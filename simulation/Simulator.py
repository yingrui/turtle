import pandas as pd

from datetime import date

from engine import Portfolio, TradeEngine
from engine.StockTradeDataEngine import StockTradeDataEngine


class Simulator:

    def __init__(self, portfolio: Portfolio, trade_engine: TradeEngine, data_engine: StockTradeDataEngine):
        self._portfolio = portfolio
        self._trade_engine = trade_engine
        self._date_engine = data_engine
        self._today = None

    def run(self, start_date, end_date):
        for day in pd.date_range(start=start_date, end=end_date):
            if self._date_engine.is_trade_day(day):
                self._today = day
                self._portfolio.update_current_price(day)
                signals = self._trade_engine.get_signals(day)

                self._trade(signals)
                print('{0}: {1}'.format(day.strftime('%Y-%m-%d'), self._portfolio))

    def _trade(self, signals):
        for signal in signals:
            if signal.status == 2:
                print(signal)
                self._portfolio.buy(signal.ts_code, self.get_close_price(signal.ts_code),
                                    max_lots_of_stock=10, position_control=0.6)
            elif signal.status == 0:
                print(signal)
                self._portfolio.sell(signal.ts_code)

    def get_close_price(self, ts_code):
        return self._date_engine.get_stock_price_on_date(ts_code, self._today)
