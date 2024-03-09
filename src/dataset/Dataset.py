import pandas as pd

from configurer import get_sql_connection


class Dataset:

    def __init__(self):
        self._sql_conn = get_sql_connection()

    def get_latest_date(self):
        df = pd.read_sql("select * from stock_trade_daily order by trade_date desc limit 0,1", con=self._sql_conn)
        return df['trade_date'][0]

