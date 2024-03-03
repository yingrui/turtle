from functools import lru_cache

import pandas as pd

from configurer import get_connection_pool


class StockTradeDataEngine:

    def __init__(self):
        self._connection_pool = get_connection_pool()

    def _read_sql(self, sql):
        sql_conn = self._connection_pool.connect()
        df = pd.read_sql(sql, con=sql_conn)
        sql_conn.close()
        return df

    @lru_cache(maxsize=96)
    def get_trade_data_by_code(self, ts_code, start_date=None, end_date=None):
        sql = 'select s.*, a.adj_factor from stock_trade_daily s ' \
              'inner join stock_adj_daily a on s.ts_code=a.ts_code and s.trade_date=a.trade_date ' \
              'where s.ts_code="{0}"'.format(ts_code)
        if start_date is not None and end_date is not None:
            sql_template = 'select s.*, a.adj_factor from stock_trade_daily s ' \
                           'inner join stock_adj_daily a on s.ts_code=a.ts_code and s.trade_date=a.trade_date ' \
                           'where s.ts_code="{0}" and s.trade_date between "{1}" and "{2}"'
            sql = sql_template.format(ts_code, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))

        df = self._read_sql(sql)
        df['trade_date'] = df['trade_date'].apply(lambda x: pd.Timestamp(x))
        return self._add_qfq(df)

    @lru_cache(maxsize=96)
    def _get_all_trade_data_by_code(self, ts_code):
        sql = 'select s.*, a.adj_factor from stock_trade_daily s ' \
              'inner join stock_adj_daily a on s.ts_code=a.ts_code and s.trade_date=a.trade_date ' \
              'where s.ts_code="{0}"'.format(ts_code)
        df = self._read_sql(sql)
        df['trade_date'] = df['trade_date'].apply(lambda x: pd.Timestamp(x))
        return df

    @staticmethod
    def _add_qfq(df):
        if not df.empty:
            last_adj_factor_at_end_date = df.adj_factor.values[-1]
            df['qfq'] = df.close * df.adj_factor / last_adj_factor_at_end_date
        return df

    def get_trade_data_by_date(self, ts_code, end_date, qfq=False, limit=500):
        df = self._get_all_trade_data_by_code(ts_code)
        if qfq and not df.empty:
            df = df[df['trade_date'] <= pd.Timestamp(end_date)].tail(limit)
            return self._add_qfq(df)

        return df[df['trade_date'] <= pd.Timestamp(end_date)].tail(limit)

    def get_stock_price_on_date(self, ts_code, end_date):
        df = self.get_trade_data_by_code(ts_code)
        last = df[df['trade_date'] <= pd.Timestamp(end_date)].tail(1)
        return last.close.values[0], last.high.values[0], last.low.values[0]

    def is_open(self, ts_code, current_date):
        sql = 'select s.ts_code, s.trade_date from stock_trade_daily s ' \
              'where s.ts_code="{0}" and s.trade_date="{1}"'.format(ts_code, current_date.strftime('%Y-%m-%d'))
        return self._read_sql(sql).shape[0] > 0

    @lru_cache(maxsize=96)
    def get_trade_data_on_date(self, day):
        sql = 'select s.*, a.adj_factor from stock_trade_daily s ' \
              'inner join stock_adj_daily a on a.ts_code=s.ts_code and a.trade_date=s.trade_date ' \
              'where s.trade_date="{0}"'.format(day.strftime('%Y-%m-%d'))
        return self._read_sql(sql)

    def get_dividents_data_on_date(self, ts_code, day):
        sql = 'select * from dividends ' \
              'where ts_code="{0}" and ex_date="{1}" and div_proc="实施"'.format(ts_code, day.strftime('%Y-%m-%d'))
        return self._read_sql(sql)

    @lru_cache(maxsize=96)
    def is_trade_day(self, day):
        sql = 'select is_open from trade_calendar where exchange="SSE" and cal_date="{0}"'.format(
            day.strftime('%Y-%m-%d'))
        df = self._read_sql(sql)
        if df.shape[0] > 0:
            return True if df['is_open'].values[0] > 0 else False
        else:
            False

    def list_stocks_on_date(self, day, ignore_st=True):
        condition = "list_status='L'"
        sql = "select * from stock where list_date<='{0}' and {1}".format(day.strftime('%Y-%m-%d'), condition)
        return self._read_sql(sql)
