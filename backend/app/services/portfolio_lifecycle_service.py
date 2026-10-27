"""Portfolio lifecycle: the pool, the decisions, and the membership history.

The daily job is deliberately two-layered, because one layer answers "which stocks deserve
attention" and the other answers "what do we do about it":

1. **Ranking → pool.** The model's top N only decides *eligibility*. A stock enters the pool as
   `watching`; it is not bought by being ranked.
2. **Rules → trades.** `watching → holding` and `holding → closed` happen when a rule fires, which is
   why a holding that drops out of the top N is **not** sold. Rules are recorded with their name and
   parameters in the event so a decision stays explainable a year later.

`dropped` is not a ranking outcome either: it means the stock left the portfolio, and only an
explicit absence rule (or a human) produces it. Rows are soft-deleted, and `joined_at`/`left_at`
record the membership interval so "which stocks were in the portfolio on day X" is a range query.

This module records **decisions**, not fills. Cash, lot sizes, costs and corporate actions belong to
the trading layer; until that exists, a `bought` event means "the rule said buy", not "we own it".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.portfolio import PortfolioStock, PortfolioStockEvent

#: `dropped` is a soft delete: the row survives so the history stays answerable.
STATUSES = ("watching", "holding", "closed", "dropped")

ACTIVE_STATUSES = ("watching", "holding")


class LifecycleError(ValueError):
    """A request the lifecycle refuses (bad portfolio, missing date, already applied)."""


@dataclass
class SelectionRules:
    """What the daily job is allowed to do. Defaults are conservative and explicit."""

    top_n: int = 50
    #: A watching stock becomes a holding when its rank is at most this. Defaults to the pool size,
    #: i.e. "it earned a place, take it".
    buy_rank_limit: int | None = None
    #: A holding is closed when its rank falls past this. Defaults to `2 × top_n`, so a stock is not
    #: sold the day it slips out of the pool.
    sell_rank_limit: int | None = None
    #: A holding is closed after this many calendar days. `None` disables the clock.
    max_holding_days: int | None = None
    #: A watching stock that has not been ranked for this many days is dropped from the portfolio.
    drop_after_absent_days: int = 30
    source: str = "simulation"

    def __post_init__(self) -> None:
        if self.top_n < 1:
            raise LifecycleError("top_n must be positive")
        # `0` means "never buy from the pool" — it must not be confused with "unset", which is why
        # these are None-checks rather than `or` defaults.
        if self.buy_rank_limit is None:
            self.buy_rank_limit = self.top_n
        if self.sell_rank_limit is None:
            self.sell_rank_limit = self.top_n * 2
        if self.buy_rank_limit > self.sell_rank_limit:
            raise LifecycleError("buy_rank_limit must not exceed sell_rank_limit")


@dataclass
class SelectionResult:
    trade_date: date
    added: list[str] = field(default_factory=list)
    resurrected: list[str] = field(default_factory=list)
    bought: list[str] = field(default_factory=list)
    sold: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    ranked: int = 0

    def as_dict(self) -> dict:
        return {
            "trade_date": self.trade_date.isoformat(),
            "ranked": self.ranked,
            "added": self.added,
            "resurrected": self.resurrected,
            "bought": self.bought,
            "sold": self.sold,
            "dropped": self.dropped,
        }


def _event(
    db: Session,
    *,
    portfolio_id: str,
    ts_code: str,
    trade_date: date,
    event: str,
    from_status: str | None,
    to_status: str | None,
    episode: int,
    score: float | None,
    rank: int | None,
    reason: str,
    rule: str | None,
    rules: SelectionRules,
    model: dict | None,
) -> PortfolioStockEvent:
    row = PortfolioStockEvent(
        portfolio_id=portfolio_id,
        ts_code=ts_code,
        trade_date=trade_date,
        event=event,
        from_status=from_status,
        to_status=to_status,
        episode=episode,
        score=None if score is None else Decimal(str(round(score, 6))),
        rank=rank,
        reason=reason,
        rule=rule,
        rule_params={
            "top_n": rules.top_n,
            "buy_rank_limit": rules.buy_rank_limit,
            "sell_rank_limit": rules.sell_rank_limit,
            "max_holding_days": rules.max_holding_days,
            "drop_after_absent_days": rules.drop_after_absent_days,
        },
        model_name=(model or {}).get("name"),
        model_version=(model or {}).get("version"),
        dataset_version=(model or {}).get("dataset_version"),
        source=rules.source,
    )
    db.add(row)
    return row


def apply_daily_selection(
    db: Session,
    *,
    portfolio_id: str,
    trade_date: date,
    rankings: list[tuple[str, float, int]],
    rules: SelectionRules | None = None,
    model: dict | None = None,
    force: bool = False,
    commit: bool = True,
) -> SelectionResult:
    """Apply one day's ranking. `rankings` is `[(ts_code, score, rank)]`, best first.

    Idempotent by construction: a second call for the same date raises unless `force=True`, because
    the job runs as a thread and a restart must not double-book a day's decisions.
    """
    rules = rules or SelectionRules()
    if not rankings:
        raise LifecycleError("no rankings for this day; refusing to clear the pool")

    already = (
        db.execute(
            select(PortfolioStockEvent.id).where(
                PortfolioStockEvent.portfolio_id == portfolio_id,
                PortfolioStockEvent.trade_date == trade_date,
            ).limit(1)
        )
    ).scalars().first()
    if already and not force:
        raise LifecycleError(
            f"selection for {trade_date} has already been applied to this portfolio; "
            "pass force=True only after deciding what to do with the recorded decisions"
        )

    result = SelectionResult(trade_date=trade_date, ranked=len(rankings))
    top = {code: (score, rank) for code, score, rank in rankings[: rules.top_n]}
    # The full ranking matters for the sell side: a holding that slid to rank 4,000 should be
    # judged on that rank, not treated as "absent from the pool".
    by_rank = {code: (score, rank) for code, score, rank in rankings}

    existing = {
        row.ts_code: row
        for row in db.execute(
            select(PortfolioStock).where(PortfolioStock.portfolio_id == portfolio_id)
        ).scalars().all()
    }

    def touch(row: PortfolioStock, status: str) -> None:
        row.status = status
        row.last_seen_in_pool = trade_date

    # --- 1. the pool: everyone ranked in the top N has a place -------------------------------
    for code, (score, rank) in top.items():
        row = existing.get(code)
        if row is None:
            row = PortfolioStock(
                portfolio_id=portfolio_id,
                ts_code=code,
                status="watching",
                joined_at=trade_date,
                episode=1,
                last_seen_in_pool=trade_date,
            )
            db.add(row)
            existing[code] = row
            result.added.append(code)
            _event(
                db,
                portfolio_id=portfolio_id,
                ts_code=code,
                trade_date=trade_date,
                event="added",
                from_status=None,
                to_status="watching",
                episode=1,
                score=score,
                rank=rank,
                reason="in_top_n",
                rule="top_n",
                rules=rules,
                model=model,
            )
        elif row.status == "dropped":
            # Soft-deleted rows come back as the same row with a new episode: the unique key on
            # (portfolio, ts_code) means a re-entry is a resurrection, never an insert.
            row.status = "watching"
            row.episode = (row.episode or 1) + 1
            row.joined_at = trade_date
            row.left_at = None
            row.dropped_at = None
            row.last_seen_in_pool = trade_date
            result.resurrected.append(code)
            _event(
                db,
                portfolio_id=portfolio_id,
                ts_code=code,
                trade_date=trade_date,
                event="resurrected",
                from_status="dropped",
                to_status="watching",
                episode=row.episode,
                score=score,
                rank=rank,
                reason="in_top_n",
                rule="top_n",
                rules=rules,
                model=model,
            )
        elif row.status == "closed":
            row.status = "watching"
            row.episode = (row.episode or 1) + 1
            row.joined_at = trade_date
            row.left_at = None
            row.last_seen_in_pool = trade_date
            result.resurrected.append(code)
            _event(
                db,
                portfolio_id=portfolio_id,
                ts_code=code,
                trade_date=trade_date,
                event="resurrected",
                from_status="closed",
                to_status="watching",
                episode=row.episode,
                score=score,
                rank=rank,
                reason="in_top_n",
                rule="top_n",
                rules=rules,
                model=model,
            )
        else:
            row.last_seen_in_pool = trade_date

    # --- 2. rules: buy, sell, and clean up the pool -----------------------------------------
    for code, row in list(existing.items()):
        score, rank = by_rank.get(code, (None, None))
        if row.status == "watching":
            if rank is not None and rank <= rules.buy_rank_limit:
                row.status = "holding"
                result.bought.append(code)
                _event(
                    db,
                    portfolio_id=portfolio_id,
                    ts_code=code,
                    trade_date=trade_date,
                    event="bought",
                    from_status="watching",
                    to_status="holding",
                    episode=row.episode or 1,
                    score=score,
                    rank=rank,
                    reason="ranked_within_buy_limit",
                    rule="buy_rank",
                    rules=rules,
                    model=model,
                )
            elif rank is None or rank > rules.sell_rank_limit:
                absent_since = row.last_seen_in_pool
                if absent_since and (trade_date - absent_since).days >= rules.drop_after_absent_days:
                    row.status = "dropped"
                    row.left_at = trade_date
                    row.dropped_at = datetime.now(timezone.utc)
                    result.dropped.append(code)
                    _event(
                        db,
                        portfolio_id=portfolio_id,
                        ts_code=code,
                        trade_date=trade_date,
                        event="dropped",
                        from_status="watching",
                        to_status="dropped",
                        episode=row.episode or 1,
                        score=score,
                        rank=rank,
                        reason=f"absent_for_{rules.drop_after_absent_days}_days",
                        rule="drop_after_absent",
                        rules=rules,
                        model=model,
                    )
        elif row.status == "holding":
            days_held = (trade_date - row.joined_at).days if row.joined_at else 0
            sold_for_rank = rank is None or rank > rules.sell_rank_limit
            sold_for_time = bool(rules.max_holding_days) and days_held >= int(rules.max_holding_days or 0)
            if sold_for_rank or sold_for_time:
                row.status = "closed"
                result.sold.append(code)
                _event(
                    db,
                    portfolio_id=portfolio_id,
                    ts_code=code,
                    trade_date=trade_date,
                    event="sold",
                    from_status="holding",
                    to_status="closed",
                    episode=row.episode or 1,
                    score=score,
                    rank=rank,
                    reason="rank_below_sell_limit" if sold_for_rank else "max_holding_days",
                    rule="sell_rank" if sold_for_rank else "max_holding_days",
                    rules=rules,
                    model=model,
                )

    if commit:
        db.commit()
    else:
        # A dry run: the caller rolls back. Committing here would make `--dry-run` a misnomer.
        db.flush()
    return result


def members_on(db: Session, portfolio_id: str, day: date) -> list[PortfolioStock]:
    """Which stocks were in the portfolio that day — a range query, not a replay."""
    return list(
        db.execute(
            select(PortfolioStock)
            .where(
                PortfolioStock.portfolio_id == portfolio_id,
                PortfolioStock.joined_at.isnot(None),
                PortfolioStock.joined_at <= day,
                (PortfolioStock.left_at.is_(None)) | (PortfolioStock.left_at > day),
            )
            .order_by(PortfolioStock.ts_code)
        ).scalars().all()
    )


def events_on(db: Session, portfolio_id: str, day: date | None = None, *, limit: int = 200) -> list[PortfolioStockEvent]:
    query = select(PortfolioStockEvent).where(PortfolioStockEvent.portfolio_id == portfolio_id)
    if day:
        query = query.where(PortfolioStockEvent.trade_date == day)
    return list(
        db.execute(
            query.order_by(PortfolioStockEvent.trade_date.desc(), PortfolioStockEvent.ts_code)
            .limit(limit)
        ).scalars().all()
    )
