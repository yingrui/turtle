"""Index data: the benchmark side of the market.

`tushare.index_basic` lists ten thousand indexes; only a handful carry daily bars (`index_daily`),
which is what a benchmark needs. A single index's daily bars are read as a normalised series so a run
can be compared with "the market" over exactly its own window.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
from sqlalchemy import text

from app.core.tushare_schema import tushare_table

#: The broad indexes worth showing on a dashboard, in display order.
BENCHMARKS = (
    ("000001.SH", "上证指数"),
    ("399001.SZ", "深证成指"),
    ("399006.SZ", "创业板指"),
    ("000300.SH", "沪深300"),
    ("000905.SH", "中证500"),
    ("000852.SH", "中证1000"),
)


class IndexService:
    def list_indexes(self, db) -> list[dict]:
        """Indexes that actually have daily bars, newest bar first — not the ten thousand names."""
        rows = db.execute(
            text(
                f"""
                SELECT b.ts_code, b.name, b.market, b.category,
                       max(d.trade_date) AS latest_date,
                       count(d.trade_date) AS bars,
                       (array_agg(d.close ORDER BY d.trade_date DESC))[1] AS last_close,
                       (array_agg(d.pct_chg ORDER BY d.trade_date DESC))[1] AS last_pct_chg
                FROM {tushare_table('index_basic')} b
                JOIN {tushare_table('index_daily')} d ON d.ts_code = b.ts_code
                GROUP BY b.ts_code, b.name, b.market, b.category
                ORDER BY bars DESC, b.ts_code
                """
            )
        ).all()
        latest = {
            code: (name, market, category, when, bars, close, pct)
            for code, name, market, category, when, bars, close, pct in rows
        }
        # The curated benchmarks first, then whatever else has data.
        ordered = []
        for code, name in BENCHMARKS:
            if code in latest:
                _name, market, category, when, bars, close, pct = latest.pop(code)
                ordered.append(self._row(code, name, market, category, when, bars, close, pct))
        for code, (name, market, category, when, bars, close, pct) in latest.items():
            ordered.append(self._row(code, name, market, category, when, bars, close, pct))
        return ordered

    @staticmethod
    def _row(
        code: str,
        name: str,
        market: str | None,
        category: str | None,
        when,
        bars: int,
        close=None,
        pct=None,
    ) -> dict:
        return {
            "ts_code": code,
            "name": name,
            "market": market,
            "category": category,
            "latest_date": when.isoformat() if when else None,
            "bars": int(bars),
            "close": _f(close),
            "pct_chg": _f(pct),
        }

    def daily(self, db, ts_code: str, start: date, end: date) -> dict:
        rows = db.execute(
            text(
                f"""
                SELECT trade_date, open, high, low, close, pre_close, pct_chg, vol, amount
                FROM {tushare_table('index_daily')}
                WHERE ts_code = :code AND trade_date BETWEEN :start AND :end
                ORDER BY trade_date
                """
            ),
            {"code": ts_code, "start": start, "end": end},
        ).all()
        return {
            "ts_code": ts_code,
            "dates": [row[0].isoformat() for row in rows],
            "open": [_f(row[1]) for row in rows],
            "high": [_f(row[2]) for row in rows],
            "low": [_f(row[3]) for row in rows],
            "close": [_f(row[4]) for row in rows],
            "pre_close": [_f(row[5]) for row in rows],
            "pct_chg": [_f(row[6]) for row in rows],
            "vol": [_f(row[7]) for row in rows],
            "amount": [_f(row[8]) for row in rows],
        }

    def benchmark_series(
        self, db, ts_code: str, dates: list[str]
    ) -> list[float | None]:
        """The index rebased to 100 on the first date, so it can share an axis with a run's equity.

        A date the index did not trade (a suspended session, or a stock's own calendar drift) keeps the
        previous value rather than punching a hole in the line.
        """
        if not dates:
            return []
        frame = pd.read_sql(
            text(
                f"""
                SELECT trade_date, close FROM {tushare_table('index_daily')}
                WHERE ts_code = :code AND trade_date BETWEEN :start AND :end
                ORDER BY trade_date
                """
            ),
            db.connection(),
            params={"code": ts_code, "start": date.fromisoformat(dates[0]), "end": date.fromisoformat(dates[-1])},
        )
        if frame.empty:
            return [None] * len(dates)
        closes = {row[0].isoformat(): float(row[1]) for row in frame.itertuples(index=False)}
        base = None
        series: list[float | None] = []
        last: float | None = None
        for day in dates:
            value = closes.get(day, last)
            if value is None:
                series.append(None)
                continue
            last = value
            if base is None:
                base = value
            series.append(round(value / base * 100, 4) if base else None)
        return series


def _f(value) -> float | None:
    return None if value is None else float(value)
