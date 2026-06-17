import pandas as pd
from sqlalchemy import text

from app.core.configurer import get_sql_connection
from app.core.tushare_schema import tushare_table as T

_STATUS_TABLES = (
    ("stock_trade_daily", "trade_date", True),
    ("daily_basic", "trade_date", True),
    ("stock_adj_daily", "trade_date", True),
    ("stock_basic", None, False),
    ("trade_calendar", "cal_date", True),
    ("dividends", "ex_date", True),
)


class Dataset:

    def get_latest_date(self):
        conn = get_sql_connection()
        try:
            row = conn.execute(
                text(f"SELECT MAX(trade_date) AS d FROM {T('stock_trade_daily')}")
            ).mappings().first()
            if row and row["d"] is not None:
                d = row["d"]
                return d.isoformat() if hasattr(d, "isoformat") else str(d)
            return None
        finally:
            conn.close()

    def get_data_status(self) -> dict:
        conn = get_sql_connection()
        try:
            tables = []
            for name, date_col, has_date in _STATUS_TABLES:
                if has_date and date_col:
                    sql = f"SELECT MAX({date_col}) AS latest, COUNT(*) AS cnt FROM {T(name)}"
                else:
                    sql = f"SELECT NULL AS latest, COUNT(*) AS cnt FROM {T(name)}"
                row = conn.execute(text(sql)).mappings().first()
                latest = row["latest"] if row else None
                if latest is not None and hasattr(latest, "isoformat"):
                    latest = latest.isoformat()
                elif latest is not None:
                    latest = str(latest)
                tables.append({
                    "name": name,
                    "latest_trade_date": latest,
                    "row_count": int(row["cnt"] or 0) if row else 0,
                })
            primary = self.get_latest_date()
            return {"as_of_date": primary, "tables": tables, "source": "external_etl"}
        finally:
            conn.close()
