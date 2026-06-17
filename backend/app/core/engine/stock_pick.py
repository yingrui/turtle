"""Fundamental stock picking from stock_basic + daily_basic."""

from __future__ import annotations

import math
from datetime import date
from typing import Any

import pandas as pd
from sqlalchemy import text

from app.core.configurer import get_sql_connection
from app.core.engine.stock_universe import get_latest_trade_date
from app.core.tushare_schema import tushare_table as T

_BASIC = T("stock_basic")
_DAILY = T("stock_trade_daily")
_DAILY_BASIC = T("daily_basic")

_SORT_COLUMNS = {
    "ts_code": "b.ts_code",
    "name": "b.name",
    "pe_ttm": "db.pe_ttm",
    "pb": "db.pb",
    "ps_ttm": "db.ps_ttm",
    "circ_mv": "db.circ_mv",
    "total_mv": "db.total_mv",
    "turnover_rate": "db.turnover_rate",
    "pct_chg": "d.pct_chg",
    "close": "db.close",
}

_LIMIT_STATUS_EXCLUDE = (-1, 2, 3, 5, 6)  # 停牌、涨停、一字涨停、跌停、一字跌停


def _float_or_none(v):
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(f) or not math.isfinite(f) else f


def pick_stocks(
    *,
    as_of_date: str | date | None = None,
    q: str | None = None,
    industry: str | None = None,
    list_status: str = "L",
    exclude_st: bool = True,
    exclude_limit: bool = True,
    pe_ttm_min: float | None = None,
    pe_ttm_max: float | None = None,
    pb_min: float | None = None,
    pb_max: float | None = None,
    ps_ttm_min: float | None = None,
    ps_ttm_max: float | None = None,
    circ_mv_min: float | None = None,
    circ_mv_max: float | None = None,
    total_mv_min: float | None = None,
    total_mv_max: float | None = None,
    turnover_rate_min: float | None = None,
    turnover_rate_max: float | None = None,
    sort: str = "circ_mv",
    order: str = "desc",
    limit: int = 200,
) -> dict:
    limit = min(max(limit, 1), 500)
    sort_col = _SORT_COLUMNS.get(sort, "db.circ_mv")
    order_sql = "DESC" if order.lower() == "desc" else "ASC"

    conn = get_sql_connection()
    try:
        if as_of_date is None:
            trade_date = get_latest_trade_date(conn)
        elif isinstance(as_of_date, date):
            trade_date = as_of_date.isoformat()
        else:
            trade_date = str(as_of_date)

        if not trade_date:
            return {"as_of_date": None, "total": 0, "items": []}

        clauses = ["b.industry IS NOT NULL", "b.industry <> ''"]
        params: dict[str, Any] = {"trade_date": trade_date, "limit": limit}

        if list_status and list_status != "all":
            clauses.append("b.list_status = :list_status")
            params["list_status"] = list_status
        if exclude_st:
            clauses.append("b.name NOT LIKE '%ST%'")
        if industry:
            clauses.append("b.industry = :industry")
            params["industry"] = industry
        if q:
            params["q"] = f"%{q.strip()}%"
            params["q_prefix"] = f"{q.strip()}%"
            clauses.append(
                "(b.ts_code ILIKE :q_prefix OR b.name ILIKE :q OR b.cnspell ILIKE :q_prefix)"
            )
        if exclude_limit:
            clauses.append(
                "(db.limit_status IS NULL OR db.limit_status NOT IN (-1, 2, 3, 5, 6))"
            )

        for field, col, vmin, vmax in (
            ("pe_ttm", "db.pe_ttm", pe_ttm_min, pe_ttm_max),
            ("pb", "db.pb", pb_min, pb_max),
            ("ps_ttm", "db.ps_ttm", ps_ttm_min, ps_ttm_max),
            ("circ_mv", "db.circ_mv", circ_mv_min, circ_mv_max),
            ("total_mv", "db.total_mv", total_mv_min, total_mv_max),
            ("turnover_rate", "db.turnover_rate", turnover_rate_min, turnover_rate_max),
        ):
            if vmin is not None:
                clauses.append(f"{col} >= :{field}_min")
                params[f"{field}_min"] = vmin
            if vmax is not None:
                clauses.append(f"{col} <= :{field}_max")
                params[f"{field}_max"] = vmax

        where_sql = " AND ".join(clauses)

        count_sql = f"""
            SELECT COUNT(*) AS cnt
            FROM {_BASIC} b
            INNER JOIN {_DAILY_BASIC} db
              ON b.ts_code = db.ts_code AND db.trade_date = :trade_date
            LEFT JOIN {_DAILY} d
              ON b.ts_code = d.ts_code AND d.trade_date = :trade_date
            WHERE {where_sql}
        """
        total = int(conn.execute(text(count_sql), params).scalar() or 0)

        list_sql = f"""
            SELECT b.ts_code, b.name, b.industry, b.market,
                   db.close, db.pe_ttm, db.pb, db.ps_ttm,
                   db.circ_mv, db.total_mv, db.turnover_rate, db.turnover_rate_f,
                   db.volume_ratio, db.limit_status,
                   d.pct_chg
            FROM {_BASIC} b
            INNER JOIN {_DAILY_BASIC} db
              ON b.ts_code = db.ts_code AND db.trade_date = :trade_date
            LEFT JOIN {_DAILY} d
              ON b.ts_code = d.ts_code AND d.trade_date = :trade_date
            WHERE {where_sql}
            ORDER BY {sort_col} {order_sql} NULLS LAST, b.ts_code ASC
            LIMIT :limit
        """
        df = pd.read_sql(text(list_sql), con=conn, params=params)
        items = []
        for row in df.to_dict(orient="records"):
            items.append({
                "ts_code": row["ts_code"],
                "name": row.get("name"),
                "industry": row.get("industry"),
                "market": row.get("market"),
                "close": _float_or_none(row.get("close")),
                "pe_ttm": _float_or_none(row.get("pe_ttm")),
                "pb": _float_or_none(row.get("pb")),
                "ps_ttm": _float_or_none(row.get("ps_ttm")),
                "circ_mv": _float_or_none(row.get("circ_mv")),
                "total_mv": _float_or_none(row.get("total_mv")),
                "turnover_rate": _float_or_none(row.get("turnover_rate")),
                "turnover_rate_f": _float_or_none(row.get("turnover_rate_f")),
                "volume_ratio": _float_or_none(row.get("volume_ratio")),
                "limit_status": int(row["limit_status"]) if row.get("limit_status") is not None else None,
                "pct_chg": _float_or_none(row.get("pct_chg")),
            })
        return {"as_of_date": trade_date, "total": total, "items": items}
    finally:
        conn.close()


PRESETS = [
    {
        "id": "low_pe",
        "name": "低市盈率",
        "name_en": "Low PE (TTM)",
        "params": {"pe_ttm_min": 0, "pe_ttm_max": 20, "sort": "pe_ttm", "order": "asc"},
    },
    {
        "id": "small_cap",
        "name": "小市值",
        "name_en": "Small cap",
        "params": {"circ_mv_min": 0, "circ_mv_max": 500000, "sort": "circ_mv", "order": "asc"},
    },
    {
        "id": "high_turnover",
        "name": "高换手",
        "name_en": "High turnover",
        "params": {"turnover_rate_min": 3, "sort": "turnover_rate", "order": "desc"},
    },
]


def get_presets() -> list[dict]:
    return PRESETS
