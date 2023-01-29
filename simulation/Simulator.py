import pandas as pd

from engine import Portfolio, TradeEngine
from engine.StockTradeDataEngine import StockTradeDataEngine


class Simulator:

    def __init__(self, portfolio: Portfolio, trade_engine: TradeEngine, data_engine: StockTradeDataEngine):
        self._portfolio = portfolio
        self._trade_engine = trade_engine
        self._date_engine = data_engine

    def run(self, start_date, end_date):
        for day in pd.date_range(start=start_date, end=end_date):
            if self._date_engine.is_trade_day(day):
                df_trade_data = self._date_engine.get_trade_data_on_date(day)

                self._portfolio.update_current_price(df_trade_data)
                self._trade(self._trade_engine.get_signals(day), df_trade_data)
                print('{0}: {1}'.format(day.strftime('%Y-%m-%d'), self._portfolio))

    def _trade(self, signals, df_trade_data):
        for signal in signals:
            close_price = df_trade_data[df_trade_data['ts_code'] == signal.ts_code]['close'].values[0]
            if signal.status == 2:
                print(signal)
                self._portfolio.buy(signal.ts_code, close_price)
            elif signal.status == 0:
                print(signal)
                self._portfolio.sell(signal.ts_code)
