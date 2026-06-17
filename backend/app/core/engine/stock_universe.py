"""Paginated stock universe queries (stock_basic + latest daily quote)."""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Any

import pandas as pd
from sqlalchemy import text

from app.core.configurer import get_sql_connection
from app.core.tushare_schema import tushare_table as T

_BASIC = T("stock_basic")
_DAILY = T("stock_trade_daily")
_DAILY_BASIC = T("daily_basic")

_SORT_COLUMNS = {
    "ts_code": "b.ts_code",
    "name": "b.name",
    "industry": "b.industry",
    "list_date": "b.list_date",
    "open": "d.open",
    "high": "d.high",
    "low": "d.low",
    "close": "d.close",
    "pct_chg": "d.pct_chg",
    "vol": "d.vol",
    "amount": "d.amount",
}

_EXCHANGE_CASE = f"""
CASE
  WHEN b.ts_code LIKE '%.SH' THEN 'SH'
  WHEN b.ts_code LIKE '%.SZ' THEN 'SZ'
  WHEN b.ts_code LIKE '%.BJ' THEN 'BJ'
  ELSE NULL
END
"""


def _build_where(
    *,
    q: str | None,
    exchange: str | None,
    market: str | None,
    industry: str | None,
    list_status: str,
    exclude_st: bool,
) -> tuple[str, dict[str, Any]]:
    clauses = ["1=1"]
    params: dict[str, Any] = {}

    if list_status and list_status != "all":
        clauses.append("b.list_status = :list_status")
        params["list_status"] = list_status

    if q:
        q = q.strip()
        params["q"] = f"%{q}%"
        params["q_prefix"] = f"{q}%"
        clauses.append(
            "(b.ts_code ILIKE :q_prefix OR b.name ILIKE :q OR b.cnspell ILIKE :q_prefix)"
        )

    if exchange:
        ex = exchange.upper()
        if ex == "SH":
            clauses.append("b.ts_code LIKE '%.SH'")
        elif ex == "SZ":
            clauses.append("b.ts_code LIKE '%.SZ'")
        elif ex == "BJ":
            clauses.append("b.ts_code LIKE '%.BJ'")

    if market:
        clauses.append("b.market = :market")
        params["market"] = market

    if industry:
        clauses.append("b.industry = :industry")
        params["industry"] = industry

    if exclude_st:
        clauses.append("b.name NOT LIKE '%ST%'")

    return " AND ".join(clauses), params


def get_latest_trade_date(conn) -> str | None:
    row = conn.execute(
        text(f"SELECT MAX(trade_date) AS d FROM {_DAILY}")
    ).mappings().first()
    if row and row["d"] is not None:
        return str(row["d"])
    return None


def _float_or_none(v) -> float | None:
    """Convert DB/pandas numeric to JSON-safe float; map NaN/Inf to None."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _row_to_item(row: dict, latest_date: str | None) -> dict:
    exchange = row.get("exchange")
    if not exchange and row.get("ts_code"):
        code = row["ts_code"]
        if code.endswith(".SH"):
            exchange = "SH"
        elif code.endswith(".SZ"):
            exchange = "SZ"
        elif code.endswith(".BJ"):
            exchange = "BJ"

    quote = None
    close = _float_or_none(row.get("quote_close"))
    if close is not None and latest_date:
        quote = {
            "trade_date": latest_date,
            "open": _float_or_none(row.get("quote_open")),
            "high": _float_or_none(row.get("quote_high")),
            "low": _float_or_none(row.get("quote_low")),
            "close": close,
            "pre_close": _float_or_none(row.get("quote_pre_close")),
            "pct_chg": _float_or_none(row.get("quote_pct_chg")),
            "vol": _float_or_none(row.get("quote_vol")),
            "amount": _float_or_none(row.get("quote_amount")),
        }

    list_date = row.get("list_date")
    if list_date is not None and not isinstance(list_date, str):
        list_date = str(list_date).replace("-", "")[:8]

    fundamentals = None
    fund_fields = (
        "pe_ttm", "pb", "ps_ttm", "circ_mv", "total_mv", "turnover_rate", "turnover_rate_f"
    )
    if any(_float_or_none(row.get(k)) is not None for k in fund_fields) or row.get("limit_status") is not None:
        fundamentals = {
            "pe_ttm": _float_or_none(row.get("pe_ttm")),
            "pb": _float_or_none(row.get("pb")),
            "ps_ttm": _float_or_none(row.get("ps_ttm")),
            "circ_mv": _float_or_none(row.get("circ_mv")),
            "total_mv": _float_or_none(row.get("total_mv")),
            "turnover_rate": _float_or_none(row.get("turnover_rate")),
            "turnover_rate_f": _float_or_none(row.get("turnover_rate_f")),
            "limit_status": int(row["limit_status"]) if row.get("limit_status") is not None and not pd.isna(row.get("limit_status")) else None,
        }

    item = {
        "ts_code": row["ts_code"],
        "symbol": row.get("symbol"),
        "name": row.get("name"),
        "industry": row.get("industry"),
        "market": row.get("market"),
        "area": row.get("area"),
        "exchange": exchange,
        "list_status": row.get("list_status"),
        "list_date": list_date,
        "quote": quote,
    }
    if fundamentals is not None:
        item["fundamentals"] = fundamentals
    return item


def list_universe(
    *,
    q: str | None = None,
    exchange: str | None = None,
    market: str | None = None,
    industry: str | None = None,
    list_status: str = "L",
    exclude_st: bool = True,
    page: int = 0,
    page_size: int = 50,
    sort: str = "ts_code",
    order: str = "asc",
) -> dict:
    page_size = min(max(page_size, 1), 100)
    page = max(page, 0)
    sort_col = _SORT_COLUMNS.get(sort, "b.ts_code")
    order_sql = "DESC" if order.lower() == "desc" else "ASC"

    where_sql, params = _build_where(
        q=q,
        exchange=exchange,
        market=market,
        industry=industry,
        list_status=list_status,
        exclude_st=exclude_st,
    )

    conn = get_sql_connection()
    try:
        latest_date = get_latest_trade_date(conn)
        params["latest_date"] = latest_date

        count_sql = f"SELECT COUNT(*) AS cnt FROM {_BASIC} b WHERE {where_sql}"
        total = int(conn.execute(text(count_sql), params).scalar() or 0)

        join_daily = ""
        select_quote = (
            "NULL AS quote_open, NULL AS quote_high, NULL AS quote_low, NULL AS quote_close, "
            "NULL AS quote_pre_close, NULL AS quote_pct_chg, NULL AS quote_vol, NULL AS quote_amount"
        )
        if latest_date:
            join_daily = f"""
            LEFT JOIN {_DAILY} d
              ON b.ts_code = d.ts_code AND d.trade_date = :latest_date
            """
            select_quote = (
                "d.open AS quote_open, d.high AS quote_high, d.low AS quote_low, d.close AS quote_close, "
                "d.pre_close AS quote_pre_close, d.pct_chg AS quote_pct_chg, d.vol AS quote_vol, "
                "d.amount AS quote_amount"
            )

        list_sql = f"""
            SELECT b.ts_code, b.symbol, b.name, b.industry, b.market, b.area, b.list_status, b.list_date,
                   {_EXCHANGE_CASE} AS exchange,
                   {select_quote}
            FROM {_BASIC} b
            {join_daily}
            WHERE {where_sql}
            ORDER BY {sort_col} {order_sql} NULLS LAST, b.ts_code ASC
            LIMIT :limit OFFSET :offset
        """
        params["limit"] = page_size
        params["offset"] = page * page_size

        df = pd.read_sql(text(list_sql), con=conn, params=params)
        items = [_row_to_item(row, latest_date) for row in df.to_dict(orient="records")]

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "as_of_date": latest_date,
            "items": items,
        }
    finally:
        conn.close()


def search_stocks(q: str, limit: int = 20) -> list[dict]:
    q = (q or "").strip()
    if not q:
        return []

    limit = min(max(limit, 1), 50)
    params: dict[str, Any] = {"q": f"%{q}%", "q_prefix": f"{q}%", "limit": limit}

    if q[0].isdigit():
        where = "(b.ts_code ILIKE :q_prefix OR b.symbol ILIKE :q_prefix)"
    else:
        where = "(b.name ILIKE :q OR b.cnspell ILIKE :q_prefix OR b.ts_code ILIKE :q_prefix)"

    sql = f"""
        SELECT b.ts_code, b.name, b.industry, {_EXCHANGE_CASE} AS exchange
        FROM {_BASIC} b
        WHERE {where}
        ORDER BY b.ts_code
        LIMIT :limit
    """

    conn = get_sql_connection()
    try:
        df = pd.read_sql(text(sql), con=conn, params=params)
        return df.to_dict(orient="records")
    finally:
        conn.close()


@lru_cache(maxsize=1)
def _meta_cache_key() -> int:
    """Bust cache every 5 minutes via time bucket."""
    import time

    return int(time.time() // 300)


@lru_cache(maxsize=4)
def _get_universe_meta_cached(_bucket: int) -> dict:
    conn = get_sql_connection()
    try:
        latest_date = get_latest_trade_date(conn)

        listed_count = conn.execute(
            text(f"SELECT COUNT(*) FROM {_BASIC} WHERE list_status = 'L'")
        ).scalar()

        ex_df = pd.read_sql(
            text(f"""
                SELECT
                  CASE
                    WHEN ts_code LIKE '%.SH' THEN 'SH'
                    WHEN ts_code LIKE '%.SZ' THEN 'SZ'
                    WHEN ts_code LIKE '%.BJ' THEN 'BJ'
                    ELSE 'OTHER'
                  END AS exchange,
                  COUNT(*) AS cnt
                FROM {_BASIC}
                WHERE list_status = 'L'
                GROUP BY 1
            """),
            con=conn,
        )
        exchanges = {row["exchange"]: int(row["cnt"]) for row in ex_df.to_dict(orient="records")}

        markets = pd.read_sql(
            text(f"""
                SELECT market, COUNT(*) AS cnt FROM {_BASIC}
                WHERE list_status = 'L' AND market IS NOT NULL AND market <> ''
                GROUP BY market ORDER BY market
            """),
            con=conn,
        )
        industries = pd.read_sql(
            text(f"""
                SELECT industry, COUNT(*) AS cnt FROM {_BASIC}
                WHERE list_status = 'L' AND industry IS NOT NULL AND industry <> ''
                GROUP BY industry ORDER BY industry
            """),
            con=conn,
        )

        return {
            "latest_trade_date": latest_date,
            "listed_count": int(listed_count or 0),
            "exchanges": exchanges,
            "markets": [row["market"] for row in markets.to_dict(orient="records") if row["market"]],
            "industries": [row["industry"] for row in industries.to_dict(orient="records") if row["industry"]],
        }
    finally:
        conn.close()


def get_universe_meta() -> dict:
    return _get_universe_meta_cached(_meta_cache_key())


def get_industry_summary(*, list_status: str = "L", exclude_st: bool = True, limit: int = 30) -> dict:
    """Circulating-market-cap weighted pct_chg by industry on the latest trade date.

    weight_i = circ_mv from daily_basic; industry change = sum(w_i * r_i) / sum(w_i).
    """
    limit = min(max(limit, 1), 100)
    where_clauses = [
        "b.industry IS NOT NULL",
        "b.industry <> ''",
        "db.circ_mv IS NOT NULL",
        "db.circ_mv > 0",
    ]
    params: dict[str, Any] = {"limit": limit}

    if list_status and list_status != "all":
        where_clauses.append("b.list_status = :list_status")
        params["list_status"] = list_status
    if exclude_st:
        where_clauses.append("b.name NOT LIKE '%ST%'")

    where_sql = " AND ".join(where_clauses)

    conn = get_sql_connection()
    try:
        latest_date = get_latest_trade_date(conn)
        if not latest_date:
            return {"as_of_date": None, "weight_by": "circ_mv", "items": []}

        params["latest_date"] = latest_date
        sql = f"""
            SELECT b.industry,
                   COUNT(*) AS stock_count,
                   SUM(db.circ_mv * d.pct_chg) / NULLIF(SUM(db.circ_mv), 0) AS avg_pct_chg,
                   SUM(CASE WHEN d.pct_chg > 0 THEN 1 ELSE 0 END) AS up_count,
                   SUM(CASE WHEN d.pct_chg < 0 THEN 1 ELSE 0 END) AS down_count,
                   SUM(db.circ_mv) AS total_circ_mv
            FROM {_BASIC} b
            INNER JOIN {_DAILY} d
              ON b.ts_code = d.ts_code AND d.trade_date = :latest_date
            INNER JOIN {_DAILY_BASIC} db
              ON b.ts_code = db.ts_code AND db.trade_date = :latest_date
            WHERE {where_sql}
            GROUP BY b.industry
            HAVING COUNT(*) >= 3
            ORDER BY avg_pct_chg DESC NULLS LAST
            LIMIT :limit
        """
        df = pd.read_sql(text(sql), con=conn, params=params)
        items = []
        for row in df.to_dict(orient="records"):
            items.append({
                "industry": row["industry"],
                "stock_count": int(row["stock_count"]),
                "avg_pct_chg": _float_or_none(row.get("avg_pct_chg")),
                "up_count": int(row["up_count"] or 0),
                "down_count": int(row["down_count"] or 0),
                "total_circ_mv": _float_or_none(row.get("total_circ_mv")),
            })
        return {"as_of_date": latest_date, "weight_by": "circ_mv", "items": items}
    finally:
        conn.close()


def get_quotes_for_codes(ts_codes: list[str]) -> list[dict]:
    """Basic info + latest quote for a list of symbols."""
    if not ts_codes:
        return []

    conn = get_sql_connection()
    try:
        latest_date = get_latest_trade_date(conn)
        params: dict[str, Any] = {"latest_date": latest_date}
        placeholders = []
        for i, code in enumerate(ts_codes):
            key = f"c{i}"
            params[key] = code
            placeholders.append(f":{key}")

        join_daily = ""
        select_quote = (
            "NULL AS quote_open, NULL AS quote_high, NULL AS quote_low, NULL AS quote_close, "
            "NULL AS quote_pre_close, NULL AS quote_pct_chg, NULL AS quote_vol, NULL AS quote_amount"
        )
        if latest_date:
            join_daily = f"""
            LEFT JOIN {_DAILY} d
              ON b.ts_code = d.ts_code AND d.trade_date = :latest_date
            """
            select_quote = (
                "d.open AS quote_open, d.high AS quote_high, d.low AS quote_low, d.close AS quote_close, "
                "d.pre_close AS quote_pre_close, d.pct_chg AS quote_pct_chg, d.vol AS quote_vol, "
                "d.amount AS quote_amount"
            )

        sql = f"""
            SELECT b.ts_code, b.symbol, b.name, b.industry, b.market, b.area, b.list_status, b.list_date,
                   {_EXCHANGE_CASE} AS exchange,
                   {select_quote}
            FROM {_BASIC} b
            {join_daily}
            WHERE b.ts_code IN ({", ".join(placeholders)})
            ORDER BY b.ts_code ASC
        """
        df = pd.read_sql(text(sql), con=conn, params=params)
        return [_row_to_item(row, latest_date) for row in df.to_dict(orient="records")]
    finally:
        conn.close()


def get_stock_snapshot(ts_code: str) -> dict | None:
    """Basic info + latest daily quote for one symbol."""
    conn = get_sql_connection()
    try:
        latest_date = get_latest_trade_date(conn)
        params: dict[str, Any] = {"ts_code": ts_code, "latest_date": latest_date}

        join_daily = ""
        select_quote = (
            "NULL AS quote_open, NULL AS quote_high, NULL AS quote_low, NULL AS quote_close, "
            "NULL AS quote_pre_close, NULL AS quote_pct_chg, NULL AS quote_vol, NULL AS quote_amount"
        )
        if latest_date:
            join_daily = f"""
            LEFT JOIN {_DAILY} d
              ON b.ts_code = d.ts_code AND d.trade_date = :latest_date
            LEFT JOIN {_DAILY_BASIC} db
              ON b.ts_code = db.ts_code AND db.trade_date = :latest_date
            """
            select_quote = (
                "d.open AS quote_open, d.high AS quote_high, d.low AS quote_low, d.close AS quote_close, "
                "d.pre_close AS quote_pre_close, d.pct_chg AS quote_pct_chg, d.vol AS quote_vol, "
                "d.amount AS quote_amount, "
                "db.pe_ttm, db.pb, db.ps_ttm, db.circ_mv, db.total_mv, db.turnover_rate, "
                "db.turnover_rate_f, db.limit_status"
            )
        else:
            select_quote = (
                "NULL AS quote_open, NULL AS quote_high, NULL AS quote_low, NULL AS quote_close, "
                "NULL AS quote_pre_close, NULL AS quote_pct_chg, NULL AS quote_vol, NULL AS quote_amount, "
                "NULL AS pe_ttm, NULL AS pb, NULL AS ps_ttm, NULL AS circ_mv, NULL AS total_mv, "
                "NULL AS turnover_rate, NULL AS turnover_rate_f, NULL AS limit_status"
            )

        sql = f"""
            SELECT b.ts_code, b.symbol, b.name, b.industry, b.market, b.area, b.list_status, b.list_date,
                   {_EXCHANGE_CASE} AS exchange,
                   {select_quote}
            FROM {_BASIC} b
            {join_daily}
            WHERE b.ts_code = :ts_code
            LIMIT 1
        """
        row = conn.execute(text(sql), params).mappings().first()
        if not row:
            return None
        return _row_to_item(dict(row), latest_date)
    finally:
        conn.close()
