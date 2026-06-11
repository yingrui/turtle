import pandas as pd

from app.core.configurer import get_sql_connection
from app.core.tushare_schema import tushare_table as T


class Dataset:

    def __init__(self):
        self._sql_conn = get_sql_connection()

    def get_latest_date(self):
        df = pd.read_sql(
            f"select trade_date from {T('stock_trade_daily')} order by trade_date desc limit 1",
            con=self._sql_conn,
        )
        if df.empty:
            return None
        return df["trade_date"].iloc[0]

