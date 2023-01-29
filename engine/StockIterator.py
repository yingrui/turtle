import pandas as pd

from configurer import get_sql_connection
from engine.Stock import Stock


class StockIterator:

    def __init__(self):
        self._sql_conn = get_sql_connection()
        self._dataframe = None

    def find_stocks_by_code(self, ts_code):
        if ts_code is not None and isinstance(ts_code, str):
            ts_code = ts_code.upper()
            df_stock = pd.read_sql("select * from stock where ts_code='{0}'".format(ts_code), con=self._sql_conn)
            return Stock(ts_code, df_stock)

    def find_stocks_by_industry(self, industry):
        if industry is not None and isinstance(industry, str):
            df_stock = pd.read_sql("select * from stock where industry='{0}'".format(industry), con=self._sql_conn)
            return self._convert_to_stock_list(df_stock)

    def find_all_stocks(self):
        df_stock = pd.read_sql("select * from stock where list_status='L'", con=self._sql_conn)
        return self._convert_to_stock_list(df_stock)

    @staticmethod
    def _convert_to_stock_list(df_stock):
        stocks = []
        for index, row in df_stock.iterrows():
            stocks.append(Stock(row.ts_code, df_stock))
        return stocks
