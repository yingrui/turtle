from functools import lru_cache

import pandas as pd

from app.core.configurer import get_sql_connection
from app.core.engine.Stock import Stock
from app.core.tushare_schema import tushare_table as T


class StockRepository:

    def __init__(self):
        self._sql_conn = get_sql_connection()
        self._dataframe = None

    def find_stock_by_code(self, ts_code):
        if ts_code is not None and isinstance(ts_code, str):
            ts_code = ts_code.upper()
            df_stock = pd.read_sql(f"select * from {T('stock_basic')} where ts_code='{ts_code}'", con=self._sql_conn)
            return Stock(ts_code, df_stock)

    def find_stock_by_name(self, name):
        if name is not None and isinstance(name, str):
            name = name.upper()
            df_stock = pd.read_sql(f"select * from {T('stock_basic')} where name like '%%{name}%%'", con=self._sql_conn)
            if df_stock.shape[0] > 0:
                ts_code = df_stock['ts_code'].values[0].upper()
                return Stock(ts_code, df_stock)
            else:
                return None

    def find_stock(self, name_or_code):
        # if name_or_code starts with digital, it is ts_code, otherwise it is name
        if name_or_code is not None and isinstance(name_or_code, str):
            if name_or_code[0].isdigit():
                return self.find_stock_by_code(name_or_code)
            else:
                return self.find_stock_by_name(name_or_code)

    def find_stocks_by_industry(self, industry):
        if industry is not None and isinstance(industry, str):
            df_stock = pd.read_sql(f"select * from {T('stock_basic')} where industry='{industry}'", con=self._sql_conn)
            return self._convert_to_stock_list(df_stock)
