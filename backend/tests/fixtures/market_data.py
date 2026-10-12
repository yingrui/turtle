"""Deterministic market-data fixture for engine tests.

Engine tests used to read the developer's PostgreSQL `tushare` schema and assert numbers that
only held for that one dataset (ATR 36.47, 3681 stocks on 2020-01-01, …). They now run against
this file-local fixture instead, so they are reproducible on a plain sqlite database.

Series shape (per stock): a linear ramp on every weekday, so prices are computable with
`close_on()` instead of being frozen by hand:

    close(day) = base + step * weekday_index(day)

`high = close + 1`, `low = close - 1`, `adj_factor = 1`, so the true range is exactly 2.0 and
`RiskController` sees ATR = 2.0. A single dividend event exists for 600519.SH on 2022-06-30 to
exercise the dividend path in `Portfolio.adjust_holding_shares`.
"""

from __future__ import annotations

from datetime import date, timedelta

SERIES_START = date(2015, 1, 1)
SERIES_END = date(2023, 12, 31)

# ts_code -> (base close on the first series day, per-day step)
SERIES = {
    "600519.SH": (1000.0, 0.5),
    "000858.SZ": (200.0, 0.25),
    "000710.SZ": (100.0, -0.2),
    "600000.SH": (10.0, 0.01),
}

STOCKS = [
    {
        "ts_code": "600519.SH",
        "symbol": "600519",
        "name": "贵州茅台",
        "area": "贵州",
        "industry": "白酒",
        "fullname": "贵州茅台酒股份有限公司",
        "market": "主板",
        "exchange": "SSE",
        "curr_type": "CNY",
        "list_status": "L",
        "list_date": "20010827",
    },
    {
        "ts_code": "000858.SZ",
        "symbol": "000858",
        "name": "五粮液",
        "area": "四川",
        "industry": "白酒",
        "fullname": "宜宾五粮液股份有限公司",
        "market": "主板",
        "exchange": "SZSE",
        "curr_type": "CNY",
        "list_status": "L",
        "list_date": "19980427",
    },
    {
        "ts_code": "000710.SZ",
        "symbol": "000710",
        "name": "贝瑞基因",
        "area": "四川",
        "industry": "医疗保健",
        "fullname": "成都市贝瑞和康基因技术股份有限公司",
        "market": "主板",
        "exchange": "SZSE",
        "curr_type": "CNY",
        "list_status": "L",
        "list_date": "19970418",
    },
    {
        "ts_code": "600000.SH",
        "symbol": "600000",
        "name": "浦发银行",
        "area": "上海",
        "industry": "银行",
        "fullname": "上海浦东发展银行股份有限公司",
        "market": "主板",
        "exchange": "SSE",
        "curr_type": "CNY",
        "list_status": "L",
        "list_date": "19991110",
    },
]

# Dividend events: (ts_code, end_date, ann_date, div_proc, stk_div, stk_bo_rate, stk_co_rate,
#                   cash_div, cash_div_tax, record_date, ex_date). record_date is the day after the
# buy date used by test_Portfolio::test_adjust_holding_shares, so the cash dividend applies.
DIVIDENDS = [
    ("600519.SH", "2021-12-31", "2022-06-01", "实施", 0.0, 0.0, 0.0, 2.0, 0.4, "2022-06-29", "2022-06-30"),
]

DDL = [
    """
    CREATE TABLE trade_calendar (
        exchange TEXT, cal_date TEXT, is_open INTEGER, pretrade_date TEXT,
        PRIMARY KEY (exchange, cal_date)
    )
    """,
    """
    CREATE TABLE stock_basic (
        ts_code TEXT PRIMARY KEY, symbol TEXT, name TEXT, area TEXT, industry TEXT,
        fullname TEXT, enname TEXT, cnspell TEXT, market TEXT, exchange TEXT, curr_type TEXT,
        list_status TEXT, list_date TEXT, delist_date TEXT, is_hs TEXT, act_name TEXT, act_ent_type TEXT
    )
    """,
    """
    CREATE TABLE stock_trade_daily (
        ts_code TEXT, trade_date TEXT, open REAL, high REAL, low REAL, close REAL,
        pre_close REAL, change REAL, pct_chg REAL, vol REAL, amount REAL,
        PRIMARY KEY (ts_code, trade_date)
    )
    """,
    """
    CREATE TABLE stock_adj_daily (
        ts_code TEXT, trade_date TEXT, adj_factor REAL, PRIMARY KEY (ts_code, trade_date)
    )
    """,
    """
    CREATE TABLE daily_basic (
        ts_code TEXT, trade_date TEXT, close REAL, turnover_rate REAL, turnover_rate_f REAL,
        volume_ratio REAL, pe REAL, pe_ttm REAL, pb REAL, ps REAL, ps_ttm REAL, dv_ratio REAL,
        dv_ttm REAL, total_share REAL, float_share REAL, free_share REAL, total_mv REAL,
        circ_mv REAL, limit_status INTEGER, PRIMARY KEY (ts_code, trade_date)
    )
    """,
    """
    CREATE TABLE dividends (
        ts_code TEXT, end_date TEXT, ann_date TEXT, div_proc TEXT, stk_div REAL,
        stk_bo_rate REAL, stk_co_rate REAL, cash_div REAL, cash_div_tax REAL, record_date TEXT,
        ex_date TEXT, pay_date TEXT, div_listdate TEXT, imp_ann_date TEXT, base_date TEXT,
        base_share REAL, update_flag TEXT, PRIMARY KEY (ts_code, ex_date)
    )
    """,
]


def trade_days(start: date = SERIES_START, end: date = SERIES_END) -> list[date]:
    """Weekdays in the window — the fixture treats every weekday as a trading day."""
    out = []
    day = start
    while day <= end:
        if day.weekday() < 5:
            out.append(day)
        day += timedelta(days=1)
    return out


def close_on(ts_code: str, day: date) -> float:
    """Close price the fixture seeds for ``ts_code`` on ``day`` (last trade day <= day)."""
    base, step = SERIES[ts_code]
    days = [d for d in trade_days() if d <= day]
    if not days:
        raise ValueError(f"{day} is before the fixture series start")
    return round(base + step * (len(days) - 1), 2)


def seed(conn) -> None:
    """(Re)create the market tables in the connected sqlite database and load the fixture."""
    for ddl in DDL:
        table = ddl.split()[2]  # "CREATE TABLE <name>"
        conn.exec_driver_sql(f"DROP TABLE IF EXISTS {table}")
        conn.exec_driver_sql(ddl)

    days = trade_days()
    conn.exec_driver_sql("INSERT INTO trade_calendar (exchange, cal_date, is_open, pretrade_date) VALUES (?, ?, ?, ?)",
                         [("SSE", d.isoformat(), 1, days[i - 1].isoformat() if i else None) for i, d in enumerate(days)])

    for stock in STOCKS:
        conn.exec_driver_sql(
            "INSERT INTO stock_basic (ts_code, symbol, name, area, industry, fullname, market, exchange, "
            "curr_type, list_status, list_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stock["ts_code"], stock["symbol"], stock["name"], stock["area"], stock["industry"],
                stock["fullname"], stock["market"], stock["exchange"], stock["curr_type"],
                stock["list_status"], stock["list_date"],
            ),
        )

    for ts_code in SERIES:
        base, step = SERIES[ts_code]
        rows, adj_rows = [], []
        for i, day in enumerate(days):
            close = round(base + step * i, 2)
            pre_close = close if i == 0 else round(base + step * (i - 1), 2)
            rows.append((ts_code, day.isoformat(), pre_close, round(close + 1, 2), round(close - 1, 2), close,
                         pre_close, round(close - pre_close, 2), round((close / pre_close - 1) * 100, 4) if pre_close else 0,
                         100000.0, 1000000.0))
            adj_rows.append((ts_code, day.isoformat(), 1.0))
        conn.exec_driver_sql(
            "INSERT INTO stock_trade_daily (ts_code, trade_date, open, high, low, close, pre_close, change, "
            "pct_chg, vol, amount) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.exec_driver_sql(
            "INSERT INTO stock_adj_daily (ts_code, trade_date, adj_factor) VALUES (?, ?, ?)", adj_rows
        )

    conn.exec_driver_sql(
        "INSERT INTO dividends (ts_code, end_date, ann_date, div_proc, stk_div, stk_bo_rate, stk_co_rate, "
        "cash_div, cash_div_tax, record_date, ex_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [tuple(row) for row in DIVIDENDS],
    )
