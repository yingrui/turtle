"""A simulation run whose book is driven by a scorecard, updated every trading day.

The existing engine trades a fixed watchlist with signal policies (`moving_average`, ATR…). This one
ranks the **whole market** each day with the monthly scorecard, keeps a top-N book, and records what
it held at every close — so "the holdings on 2026-05-14" is a lookup inside the run, not something
that only exists if someone ran a script that day.

Rules, all explicit so a run can be explained and reproduced:

- **Pool**: the day's top `top_n` by score (ST/delisting excluded before ranking).
- **Buy**: a pooled name is bought when there is cash, up to `target_weight` of current equity.
- **Sell**: when its rank falls past `sell_rank_limit` (default 2 × top_n) or it is held longer than
  `max_holding_days`. Falling out of the pool alone does not sell — the pool decides eligibility, the
  rule decides trades.
- **Sizing**: equal weight, whole lots of 100 shares, `cash_buffer` kept aside, commission on both
  sides and stamp duty on sells.

The run never touches `portfolio_stocks`: the live portfolio and a backtest are different books.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

import numpy as np
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.factor.score import ModelUnavailable, load_model_for, rank_cross_section, score_frame
from app.models.portfolio import PortfolioTransaction
from app.models.simulation import SimulationDaily, SimulationHolding, SimulationRun

LOT = 100
COMMISSION_RATE = 0.0003
COMMISSION_MIN = 5.0
STAMP_DUTY_RATE = 0.001


@dataclass
class ModelRunConfig:
    """Everything that changes the outcome, recorded in the run's config snapshot."""

    policy: str = "expanding"          # which model directory under reports/models
    top_n: int = 50
    sell_rank_limit: int | None = None
    max_holding_days: int | None = None
    cash_buffer: float = 0.05
    min_price: float = 2.0             # ignore penny/newly-listed noise
    exclude_st: bool = True

    def __post_init__(self) -> None:
        if self.top_n < 1:
            raise ValueError("top_n must be positive")
        if self.sell_rank_limit is None:
            self.sell_rank_limit = self.top_n * 2
        if self.sell_rank_limit < self.top_n:
            raise ValueError("sell_rank_limit must not be below top_n")

    def as_dict(self) -> dict:
        return {
            "policy": self.policy,
            "top_n": self.top_n,
            "sell_rank_limit": self.sell_rank_limit,
            "max_holding_days": self.max_holding_days,
            "cash_buffer": self.cash_buffer,
            "min_price": self.min_price,
            "exclude_st": self.exclude_st,
        }


@dataclass
class _Position:
    shares: int
    cost: float
    opened: date
    last_rank: int | None = None
    last_score: float | None = None


@dataclass
class ModelRunResult:
    run_id: str
    days: int = 0
    trades: int = 0
    final_equity: float = 0.0
    holdings_rows: int = 0
    skipped_days: list[str] = field(default_factory=list)


def _trade_days(db: Session, start: date, end: date) -> list[date]:
    return [
        row[0]
        for row in db.execute(
            text(
                "SELECT DISTINCT trade_date FROM tushare.stock_trade_daily "
                "WHERE trade_date BETWEEN :s AND :e ORDER BY trade_date"
            ),
            {"s": start, "e": end},
        ).all()
    ]


def _closes(db: Session, day: date) -> dict[str, float]:
    return {
        row[0]: float(row[1])
        for row in db.execute(
            text("SELECT ts_code, close FROM tushare.stock_trade_daily WHERE trade_date = :d"),
            {"d": day},
        ).all()
    }


def _st_codes(db: Session) -> set[str]:
    return {
        row[0]
        for row in db.execute(
            text(
                "SELECT ts_code FROM tushare.stock_basic "
                "WHERE name LIKE '%ST%' OR name LIKE '%退%' OR name LIKE '%退市%'"
            )
        ).all()
    }


def run_model_simulation(
    db: Session,
    *,
    run: SimulationRun,
    start: date,
    end: date,
    initial_cash: float,
    config: ModelRunConfig,
    on_day=None,
) -> ModelRunResult:
    """Walk the window once, trading daily, recording equity and positions for every close."""
    result = ModelRunResult(run_id=run.id)
    cash = float(initial_cash)
    positions: dict[str, _Position] = {}
    st_codes = _st_codes(db) if config.exclude_st else set()

    for day in _trade_days(db, start, end):
        try:
            model = load_model_for(day, config.policy)
        except ModelUnavailable as exc:
            result.skipped_days.append(f"{day}: {exc}")
            continue
        codes = [factor["code"] for factor in model["factors"]]
        ranks = rank_cross_section(db, day, codes)
        if ranks.empty:
            result.skipped_days.append(f"{day}: no factor values")
            continue

        ranked = ranks[~ranks["ts_code"].isin(st_codes)].reset_index(drop=True)
        if ranked.empty:
            result.skipped_days.append(f"{day}: nothing left after the ST filter")
            continue
        ranked["score"] = score_frame(model, ranked.drop(columns=["ts_code"]))
        ranked = ranked.sort_values("score", ascending=False).reset_index(drop=True)
        ranked["rank"] = ranked.index + 1
        best = ranked.set_index("ts_code")[["rank", "score"]]
        closes = _closes(db, day)

        # 1) sells: rank past the limit, or held too long
        for code in list(positions):
            position = positions[code]
            rank = int(best["rank"].get(code, 10**9))
            price = closes.get(code)
            if price is None or price < config.min_price:
                continue
            too_far = rank > config.sell_rank_limit
            too_long = bool(config.max_holding_days) and (day - position.opened).days >= int(config.max_holding_days or 0)
            if not (too_far or too_long):
                continue
            amount = price * position.shares
            fee = max(COMMISSION_MIN, amount * COMMISSION_RATE)
            tax = amount * STAMP_DUTY_RATE
            cash += amount - fee - tax
            result.trades += 1
            db.add(
                PortfolioTransaction(
                    portfolio_id=run.portfolio_id,
                    simulation_run_id=run.id,
                    ts_code=code,
                    trade_date=day,
                    side="sell",
                    shares=position.shares,
                    price=Decimal(str(price)),
                    amount=Decimal(str(round(amount, 2))),
                    fee=Decimal(str(round(fee, 2))),
                    tax=Decimal(str(round(tax, 2))),
                    realized_pnl=Decimal(str(round((price - position.cost) * position.shares, 2))),
                    reason="rank_below_sell_limit" if too_far else "max_holding_days",
                    source="simulation",
                )
            )
            del positions[code]

        # 2) buys: pooled names, equal weight, whole lots, keeping the buffer aside
        equity = cash + sum(
            position.shares * closes.get(code, position.cost) for code, position in positions.items()
        )
        target = equity * (1 - config.cash_buffer) / config.top_n
        for row in ranked.head(config.top_n).itertuples():
            code = row.ts_code
            if code in positions:
                continue
            price = closes.get(code)
            if price is None or price < config.min_price:
                continue
            shares = int(target // (price * LOT)) * LOT
            if shares <= 0:
                continue
            amount = price * shares
            fee = max(COMMISSION_MIN, amount * COMMISSION_RATE)
            if amount + fee > cash:
                continue
            cash -= amount + fee
            positions[code] = _Position(shares=shares, cost=price, opened=day, last_rank=int(row.rank), last_score=float(row.score))
            result.trades += 1
            db.add(
                PortfolioTransaction(
                    portfolio_id=run.portfolio_id,
                    simulation_run_id=run.id,
                    ts_code=code,
                    trade_date=day,
                    side="buy",
                    shares=shares,
                    price=Decimal(str(price)),
                    amount=Decimal(str(round(amount, 2))),
                    fee=Decimal(str(round(fee, 2))),
                    reason="in_top_n",
                    source="simulation",
                )
            )

        # 3) the book at the close, recorded so any date can be inspected later
        priced = {code: closes.get(code, position.cost) for code, position in positions.items()}
        equity = cash + sum(position.shares * priced[code] for code, position in positions.items())
        for code, position in positions.items():
            price = priced[code]
            value = position.shares * price
            rank = best["rank"].get(code)
            score = best["score"].get(code)
            db.add(
                SimulationHolding(
                    run_id=run.id,
                    trade_date=day,
                    ts_code=code,
                    shares=position.shares,
                    price=Decimal(str(price)),
                    market_value=Decimal(str(round(value, 2))),
                    weight=Decimal(str(round(value / equity, 6))) if equity else None,
                    rank=int(rank) if rank is not None else None,
                    score=Decimal(str(round(float(score), 6))) if score is not None else None,
                )
            )
            position.last_rank = int(rank) if rank is not None else None
            position.last_score = float(score) if score is not None else None
            result.holdings_rows += 1
        db.add(
            SimulationDaily(
                run_id=run.id,
                trade_date=day,
                return_rate=Decimal(str(round(equity / initial_cash * 100, 6))),
                balance=Decimal(str(round(cash, 2))),
                benefit=Decimal(str(round(equity - initial_cash, 2))),
                investment_total=Decimal(str(round(equity - cash, 2))),
                total=Decimal(str(round(equity, 2))),
            )
        )
        result.days += 1
        result.final_equity = equity
        db.flush()
        if on_day is not None:
            on_day(day, equity, cash, len(positions))

    return result


def summarise(db: Session, run_id: str) -> dict:
    """Fill the run's stored summary from the daily rows it just wrote."""
    daily = db.execute(
        text("SELECT trade_date, total FROM simulation_daily WHERE run_id = :r ORDER BY trade_date"),
        {"r": run_id},
    ).all()
    if not daily:
        return {}
    totals = [float(row[1]) for row in daily]
    peak, worst = totals[0], 0.0
    for value in totals:
        peak = max(peak, value)
        worst = min(worst, value / peak - 1)
    first, last = totals[0], totals[-1]
    return {
        "window_start": daily[0][0],
        "window_end": daily[-1][0],
        "initial_total": first,
        "final_total": last,
        "return_rate_pct": last / first * 100,
        "max_drawdown_pct": round(worst * 100, 2),
        "years": 1,
        "trade_count": db.scalar(
            select(func.count()).select_from(PortfolioTransaction).where(
                PortfolioTransaction.simulation_run_id == run_id
            )
        ),
    }


def holdings_on(db: Session, run_id: str, day: date) -> list[SimulationHolding]:
    return list(
        db.execute(
            select(SimulationHolding)
            .where(SimulationHolding.run_id == run_id, SimulationHolding.trade_date == day)
            .order_by(SimulationHolding.market_value.desc())
        ).scalars().all()
    )


def holding_dates(db: Session, run_id: str) -> list[date]:
    return [row[0] for row in db.execute(
        select(SimulationHolding.trade_date).where(SimulationHolding.run_id == run_id)
        .distinct().order_by(SimulationHolding.trade_date)
    ).all()]
