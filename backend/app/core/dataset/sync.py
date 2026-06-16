"""Data sync routines callable from API (no subprocess)."""

from __future__ import annotations

import time
from datetime import date
from typing import Callable

import pandas as pd

from app.core.configurer import get_sql_connection, get_ts_api
from app.core.tushare_schema import TUSHARE_SCHEMA
from app.core.util.sql_methods import insert_or_update

LogFn = Callable[[str], None]


def _log(msg: str, log_fn: LogFn | None = None) -> None:
    print(msg)
    if log_fn:
        log_fn(msg)


def download_stock_trade_data(ts_api, sql_conn, day, log_fn: LogFn | None = None) -> int:
    df = ts_api.query("daily", ts_code="", start_date=day.strftime("%Y%m%d"), end_date=day.strftime("%Y%m%d"))
    count = df.to_sql(
        con=sql_conn,
        name="stock_trade_daily",
        schema=TUSHARE_SCHEMA,
        index=False,
        if_exists="append",
        method=insert_or_update,
    )
    _log(f"{day.strftime('%Y-%m-%d')}, {count} trade data", log_fn)
    time.sleep(1)
    return count


def download_stock_adj_data(ts_api, sql_conn, day, log_fn: LogFn | None = None) -> int:
    df = ts_api.query("adj_factor", ts_code="", trade_date=day.strftime("%Y%m%d"))
    count = df.to_sql(
        con=sql_conn, name="stock_adj_daily", schema=TUSHARE_SCHEMA, index=False, if_exists="append", method=insert_or_update
    )
    _log(f"{day.strftime('%Y-%m-%d')}, {count} restoration data", log_fn)
    time.sleep(1)
    return count


def download_dividends_data(ts_api, sql_conn, day, log_fn: LogFn | None = None) -> int:
    df = ts_api.query("dividend", ts_code="", ex_date=day.strftime("%Y%m%d"))
    count = df.to_sql(
        con=sql_conn, name="dividends", schema=TUSHARE_SCHEMA, index=False, if_exists="append", method=insert_or_update
    )
    _log(f"{day.strftime('%Y-%m-%d')}, {count} dividends data", log_fn)
    time.sleep(1)
    return count


def download_daily_basic_data(ts_api, sql_conn, day, log_fn: LogFn | None = None) -> int:
    df = ts_api.query("daily_basic", trade_date=day.strftime("%Y%m%d"))
    count = df.to_sql(
        con=sql_conn,
        name="daily_basic",
        schema=TUSHARE_SCHEMA,
        index=False,
        if_exists="append",
        method=insert_or_update,
    )
    _log(f"{day.strftime('%Y-%m-%d')}, {count} daily_basic data", log_fn)
    time.sleep(1)
    return count


def update_stock_list(ts_api, sql_conn, log_fn: LogFn | None = None) -> int:
    fields = (
        "ts_code,symbol,name,area,industry,fullname,enname,cnspell,market,exchange,"
        "curr_type,list_status,list_date,delist_date,is_hs,act_name,act_ent_type"
    )
    df = ts_api.query("stock_basic", exchange="", fields=fields)
    count = df.to_sql(
        con=sql_conn, name="stock_basic", schema=TUSHARE_SCHEMA, index=False, if_exists="append", method=insert_or_update
    )
    _log(f"update count: {count}", log_fn)
    time.sleep(1)
    return count


def sync_stock_data(
    start: date,
    end: date | None = None,
    *,
    trade_data: bool = True,
    adj_data: bool = True,
    daily_basic: bool = True,
    dividend: bool = True,
    log_fn: LogFn | None = None,
) -> None:
    end = end or start
    ts_api = get_ts_api()
    sql_conn = get_sql_connection()
    update_stock_list(ts_api, sql_conn, log_fn)
    for day in pd.date_range(start=start, end=end):
        if day.dayofweek < 5:
            if trade_data:
                download_stock_trade_data(ts_api, sql_conn, day, log_fn)
            if adj_data:
                download_stock_adj_data(ts_api, sql_conn, day, log_fn)
            if daily_basic:
                download_daily_basic_data(ts_api, sql_conn, day, log_fn)
            if dividend:
                download_dividends_data(ts_api, sql_conn, day, log_fn)


def sync_trade_calendar(
    start_year: int,
    end_year: int | None = None,
    *,
    log_fn: LogFn | None = None,
) -> None:
    """Sync exchange trade calendars (SSE, SZSE) for year range."""
    end_year = end_year or start_year
    ts_api = get_ts_api()
    sql_conn = get_sql_connection()
    for exchange in ("SSE", "SZSE"):
        for year in range(start_year, end_year + 1):
            _log(f"Updating trade calendar for {exchange} {year}", log_fn)
            df = ts_api.query(
                "trade_cal",
                exchange=exchange,
                start_date=f"{year}0101",
                end_date=f"{year}1231",
                fields="exchange,cal_date,is_open,pretrade_date",
            )
            df.to_sql(
                con=sql_conn,
                name="trade_calendar",
                schema=TUSHARE_SCHEMA,
                index=False,
                if_exists="append",
                method=insert_or_update,
            )
            time.sleep(1)
