from functools import lru_cache

import pandas as pd

from configurer import get_sql_connection


class StockTradeDataEngine:

    def __init__(self):
        self._sql_conn = get_sql_connection()

    @lru_cache(maxsize=32)
    def get_trade_data_by_code(self, ts_code, start_date=None, end_date=None):
        sql = 'select * from stock_trade_daily where ts_code="{0}"'.format(ts_code)
        if start_date is not None and end_date is not None:
            sql_template = 'select * from stock_trade_daily where ts_code="{0}" and trade_date between "{1}" and "{2}"'
            sql = sql_template.format(ts_code, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
        df = pd.read_sql(sql, con=self._sql_conn)
        df['trade_date'] = df['trade_date'].apply(lambda x: pd.Timestamp(x))
        return df

    def get_trade_data_by_date(self, ts_code, end_date, limit=500):
        df = self.get_trade_data_by_code(ts_code)
        return df[df['trade_date'] < end_date].tail(limit)

    @lru_cache(maxsize=32)
    def get_trade_data_on_date(self, day):
        sql = 'select * from stock_trade_daily where trade_date="{0}"'.format(day.strftime('%Y-%m-%d'))
        return pd.read_sql(sql, con=self._sql_conn)

    def is_trade_day(self, day):
        sql = 'select is_open from trade_calendar where exchange="SSE" and cal_date="{0}"'.format(
            day.strftime('%Y-%m-%d'))
        df = pd.read_sql(sql, con=self._sql_conn)
        if df.shape[0] > 0:
            return True if df['is_open'].values[0] > 0 else False
        else:
            False
