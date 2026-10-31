"""A simulation whose **pool** comes from a ranking and whose **trades** come from the policy.

The model run in `model_runner` buys the top-N outright — that measures the ranking, not the strategy.
What a portfolio actually does is: the ranking nominates a pool, and the configured policy decides
whether to buy or sell. This runner implements that second half by reusing the existing engine
(`TradeSignalMonitor`), so the rules are the same ones the signal runs use.

Sizing and bookkeeping stay here (equal weight, whole lots, fees, stamp duty, daily holdings), because
they are the same for every pool source.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.engine.StockTradeDataEngine import StockTradeDataEngine
from app.core.engine.TradeSignalMonitor import TradeSignalMonitor
from app.core.simulation.model_runner import (
    COMMISSION_MIN,
    COMMISSION_RATE,
    LOT,
    STAMP_DUTY_RATE,
    _closes,
    _trade_days,
    next_open,
    summarise,
)
from app.core.market.tradability import judge, market_context
from app.core.simulation.ranking import RankingProvider
from app.models.portfolio import PortfolioPolicy
from app.models.simulation import SimulationDaily, SimulationHolding, SimulationPool, SimulationTrade


@dataclass
class PolicyRunConfig:
    policy_id: int = 0
    top_n: int = 50
    cash_buffer: float = 0.05
    max_new_per_day: int | None = None
    #: Buy on entering the pool, let the policy decide only the exit.
    #: A `moving_average` policy is built for a fixed watchlist: its golden cross rarely lands while a
    #: rotating pool member is in the pool, so "pool → policy decides both sides" trades almost never.
    enter_on_pool: bool = False

    def as_dict(self) -> dict:
        return {
            "policy_id": self.policy_id,
            "top_n": self.top_n,
            "cash_buffer": self.cash_buffer,
            "max_new_per_day": self.max_new_per_day,
            "enter_on_pool": self.enter_on_pool,
        }


def _policy_params(db: Session, portfolio_id: str) -> tuple[dict, dict]:
    """The portfolio's policy parameters and risk control, as the signal engine expects them."""
    from app.models.portfolio import PortfolioRiskControl

    policy = db.scalar(
        select(PortfolioPolicy)
        .where(PortfolioPolicy.portfolio_id == portfolio_id)
        .order_by(PortfolioPolicy.id)
    )
    risk = db.scalar(select(PortfolioRiskControl).where(PortfolioRiskControl.portfolio_id == portfolio_id))
    policy_params = dict(policy.params or {}) if policy else {}
    risk_params = {}
    if risk:
        risk_params = {
            "bearable_trading_loss": float(risk.bearable_trading_loss or 0),
            "position_control": float(risk.position_control or 1),
            "max_position_size": int(risk.max_position_size or 0),
            "max_position_ratio": float(risk.max_position_ratio or 0),
            "stop_loss_point.should_check": bool(risk.stop_loss_should_check),
            "stop_loss_point.n_times_atr": float(risk.stop_loss_n_times_atr or 0),
            "stop_loss_point.should_update": bool(risk.stop_loss_should_update),
            "max_holding_period.should_check": bool(risk.max_holding_should_check),
            "max_holding_period.days": int(risk.max_holding_days or 0),
        }
    return {**policy_params, **risk_params}, policy_params


def run_policy_simulation(
    db: Session,
    *,
    run,
    start: date,
    end: date,
    initial_cash: float,
    config: PolicyRunConfig,
    provider: RankingProvider,
    on_day=None,
) -> dict:
    """Pool from the ranking, entries/exits from the policy, sizing and books here."""
    cash = float(initial_cash)
    positions: dict[str, int] = {}
    engine = StockTradeDataEngine()
    params_all, _ = _policy_params(db, run.portfolio_id)
    # Record the parameters that actually drove the signals. Whether a policy run traded 29 times or
    # 6,492 is a question about these values; a run record that omits them cannot be audited.
    import json as _json

    snapshot = run.config_snapshot
    snapshot = dict(snapshot) if isinstance(snapshot, dict) else _json.loads(snapshot or "{}")
    snapshot["policy_params"] = params_all
    run.config_snapshot = _json.dumps(snapshot, ensure_ascii=False)
    days = 0
    trades = 0
    rejected: dict[str, int] = {}

    last_seen: dict[str, float] = {}

    for day in _trade_days(db, start, end):
        ranked = provider.rankings(db, day)
        if not ranked:
            continue
        pool = [item.ts_code for item in ranked[: config.top_n]]
        best = {item.ts_code: (item.rank, item.score) for item in ranked}
        closes = _closes(db, day)
        # A suspended stock has no row today: value it at its last known close, not at zero. Zeroing
        # it would tank the equity curve on every suspension day and corrupt every weight computed
        # from it.
        last_seen.update(closes)

        def equity_now() -> float:
            """Cash plus every **currently** held position.

            Valuing a snapshot taken before the day's trades understated equity on any day that opened
            positions — on a day with 50 entries the curve reported only the leftover cash, which the
            benchmark view then used as the base and turned a loss into a doubling.
            """
            return cash + sum(
                held * closes.get(code, last_seen.get(code, 0.0)) for code, held in positions.items()
            )
        fills = next_open(db, day)          # execute at the next open, value at today's close
        context = market_context(db, day, sorted(set(pool) | set(positions)))

        def tradable(code: str, side: str, price: float | None) -> bool:
            info = context.get(code, {})
            verdict = judge(
                side=side, ts_code=code, price=price,
                pre_close=info.get("pre_close"), listed_days=info.get("listed_days"),
                name=info.get("name"),
            )
            if not verdict.ok:
                rejected[verdict.reason] = rejected.get(verdict.reason, 0) + 1
            return verdict.ok
        # The policy watches the pool **and** what is already held: a position that fell out of the
        # pool still needs its sell signal.
        watch = sorted(set(pool) | set(positions))
        signals = TradeSignalMonitor(engine, watch, params_all).detect_signals(day)

        for signal in signals:
            code = signal.ts_code
            price = fills.get(code)
            if price is None:
                continue
            if signal.status == "sell" and positions.get(code) and tradable(code, "sell", price):
                shares = positions.pop(code)
                amount = price * shares
                fee = max(COMMISSION_MIN, amount * COMMISSION_RATE)
                tax = amount * STAMP_DUTY_RATE
                cash += amount - fee - tax
                trades += 1
                db.add(
                    SimulationTrade(
                        id=str(uuid.uuid4()), run_id=run.id, ts_code=code, trade_date=day,
                        side="sell", shares=shares, price=Decimal(str(price)),
                        amount=Decimal(str(round(amount, 2))), fee=Decimal(str(round(fee, 2))),
                        tax=Decimal(str(round(tax, 2))), reason=f"policy:{signal.status}",
                    )
                )
            elif (
                signal.status == "buy"
                and code not in positions
                and not config.enter_on_pool
                and tradable(code, "buy", price)
            ):
                equity = equity_now()
                target = equity * (1 - config.cash_buffer) / config.top_n
                shares = int(target // (price * LOT)) * LOT
                if shares <= 0:
                    continue
                amount = price * shares
                fee = max(COMMISSION_MIN, amount * COMMISSION_RATE)
                if amount + fee > cash:
                    continue
                cash -= amount + fee
                positions[code] = shares
                last_seen.setdefault(code, price)   # a session without a close still has this price
                trades += 1
                db.add(
                    SimulationTrade(
                        id=str(uuid.uuid4()), run_id=run.id, ts_code=code, trade_date=day,
                        side="buy", shares=shares, price=Decimal(str(price)),
                        amount=Decimal(str(round(amount, 2))), fee=Decimal(str(round(fee, 2))),
                        reason=f"policy:{signal.status}",
                    )
                )

        if config.enter_on_pool:
            # Entry is the pool's decision; the policy above only produced exits.
            for code in pool:
                if code in positions or len(positions) >= config.top_n:
                    continue
                price = fills.get(code)
                if price is None or not tradable(code, "buy", price):
                    continue
                equity = equity_now()
                target = equity * (1 - config.cash_buffer) / config.top_n
                shares = int(target // (price * LOT)) * LOT
                if shares <= 0:
                    continue
                amount = price * shares
                fee = max(COMMISSION_MIN, amount * COMMISSION_RATE)
                if amount + fee > cash:
                    continue
                cash -= amount + fee
                positions[code] = shares
                last_seen.setdefault(code, price)   # a session without a close still has this price
                trades += 1
                db.add(
                    SimulationTrade(
                        id=str(uuid.uuid4()), run_id=run.id, ts_code=code, trade_date=day,
                        side="buy", shares=shares, price=Decimal(str(price)),
                        amount=Decimal(str(round(amount, 2))), fee=Decimal(str(round(fee, 2))),
                        reason="pool_entry",
                    )
                )

        for code in pool:
            rank, score = best[code]
            db.add(
                SimulationPool(
                    run_id=run.id, trade_date=day, ts_code=code, rank=rank,
                    score=Decimal(str(round(score, 6))), held=code in positions,
                )
            )
        equity = equity_now()
        for code, shares in positions.items():
            price = closes.get(code, last_seen.get(code, 0.0))
            db.add(
                SimulationHolding(
                    run_id=run.id, trade_date=day, ts_code=code, shares=shares,
                    price=Decimal(str(price)), market_value=Decimal(str(round(shares * price, 2))),
                    weight=Decimal(str(round(shares * price / equity, 6))) if equity else None,
                    rank=best.get(code, (None, None))[0],
                    score=(
                        Decimal(str(round(best[code][1], 6))) if code in best else None
                    ),
                )
            )
        db.add(
            SimulationDaily(
                run_id=run.id, trade_date=day,
                return_rate=Decimal(str(round(equity / initial_cash * 100, 6))),
                balance=Decimal(str(round(cash, 2))),
                benefit=Decimal(str(round(equity - initial_cash, 2))),
                investment_total=Decimal(str(round(equity - cash, 2))),
                total=Decimal(str(round(equity, 2))),
            )
        )
        days += 1
        db.flush()
        if on_day:
            on_day(day, equity, cash, len(positions))

    # Cash alone is not the ending value — the book still holds positions. `held * 0.0` here reported
    # 249,926 for an account that closed at 962,155 and made a −5.6% run look like a −75% one.
    final_equity = equity_now()
    return {
        "days": days,
        "trades": trades,
        "final_equity": final_equity,
        "holdings": len(positions),
        "rejected_fills": rejected,
    }
