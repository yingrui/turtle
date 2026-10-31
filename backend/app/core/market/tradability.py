"""What can actually be traded today.

A ranking answers "which stock looks best"; not "can I buy it". Suspended stocks cannot be traded, a
limit-up open cannot be bought, a limit-down open cannot be sold, and a stock on its first listing day
cannot be bought. Without these rules a backtest books fills that never existed.

One module, three call sites (pool, buys, sells) — they must not drift apart.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

#: Price limits by board: STAR/ChiNext 20%, ST 5%, the rest 10%.
LIMIT_20 = ("688", "300", "301")


@dataclass(frozen=True)
class Tradability:
    ok: bool
    reason: str = ""


def limit_ratio(ts_code: str, name: str | None = None) -> float:
    if name and "ST" in name:
        return 0.05
    if ts_code.startswith(LIMIT_20):
        return 0.20
    return 0.10


def judge(
    *,
    side: str,
    ts_code: str,
    price: float | None,
    pre_close: float | None,
    listed_days: int | None,
    name: str | None = None,
) -> Tradability:
    """`side` is `buy` or `sell`; everything it needs is passed in, so it is testable."""
    if price is None:
        return Tradability(False, "suspended")
    if name and "退" in name:
        return Tradability(False, "delisting")
    if listed_days is not None and listed_days < 1:
        return Tradability(False, "first_day_listing")
    if pre_close:
        ratio = limit_ratio(ts_code, name)
        high = round(pre_close * (1 + ratio), 2)
        low = round(pre_close * (1 - ratio), 2)
        if side == "buy" and price >= high:
            return Tradability(False, "limit_up")
        if side == "sell" and price <= low:
            return Tradability(False, "limit_down")
    return Tradability(True)


def market_context(db: Session, day: date, codes: list[str]) -> dict[str, dict]:
    """`pre_close`, `name` and `listed_days` for those codes on `day`."""
    if not codes:
        return {}
    from app.core.tushare_schema import tushare_table

    rows = db.execute(
        text(
            f"SELECT d.ts_code, d.pre_close, b.name, b.list_date "
            f"FROM {tushare_table('stock_trade_daily')} d "
            f"LEFT JOIN {tushare_table('stock_basic')} b ON b.ts_code = d.ts_code "
            "WHERE d.trade_date = :day"
        ),
        {"day": day},
    ).all()
    context: dict[str, dict] = {}
    for ts_code, pre_close, name, list_date in rows:
        listed_days = (day - _as_date(list_date)).days if list_date else None
        context[ts_code] = {
            "pre_close": float(pre_close) if pre_close is not None else None,
            "name": name,
            "listed_days": listed_days,
        }
    return {code: context[code] for code in codes if code in context}


def _as_date(value) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])
