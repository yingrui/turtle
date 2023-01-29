import time

import pandas as pd
from engine import Portfolio, TradeEngine
from engine.StockTradeDataEngine import StockTradeDataEngine


class Simulator:

    def __init__(self, portfolio: Portfolio, trade_engine: TradeEngine):
        self._portfolio = portfolio
        self._trade_engine = trade_engine
        self._date_engine = StockTradeDataEngine()

    def run(self, start_date, end_date):
        for day in pd.date_range(start=start_date, end=end_date):
            if self._date_engine.is_trade_day(day):
                print(day.strftime('%Y-%m-%d'))
                df_trade_data = self._date_engine.get_trade_data_on_date(day)

                self._portfolio.update_current_price(df_trade_data)
                self._trade(self._trade_engine.get_signals(), df_trade_data)
                print(self._portfolio)
            # time.sleep(1)

    def _trade(self, signals, df_trade_data):
        for signal in signals:
            close_price = df_trade_data[df_trade_data['ts_code'] == signal.ts_code]['close'].values[0]
            if signal.status == 2:
                self._portfolio.buy(signal.ts_code, close_price)
            else:
                self._portfolio.sell(signal.ts_code)
