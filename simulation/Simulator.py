import pandas as pd

from engine import Portfolio, TradeSignalMonitor
from engine.InvestmentLogger import InvestmentLogger
from engine.RiskController import RiskController
from engine.StockTradeDataEngine import StockTradeDataEngine


class Simulator:

    def __init__(self, portfolio: Portfolio, trade_monitor: TradeSignalMonitor, data_engine: StockTradeDataEngine,
                 parameters={}):
        self._portfolio = portfolio
        self._trade_monitor = trade_monitor
        self._data_engine = data_engine
        self._today = None
        self._logger = InvestmentLogger(portfolio.name)
        self._risk_controller = RiskController(portfolio, parameters)
        self._position_control = parameters.get('risk_control.position_control', 1)
        self._max_position_size = parameters.get('risk_control.max_position_size', 10)

    def run(self, start_date, end_date):
        for day in pd.date_range(start=start_date, end=end_date):
            if self._data_engine.is_trade_day(day):
                self._today = day
                signals = self._trade_monitor.detect_signals(day)
                self._trade(signals, day)
                self._logger.log(portfolio=self._portfolio, current_date=day)
                print('{0}| {1}'.format(day.strftime('%Y-%m-%d'), self._portfolio))
        initial_total, total, years, cagr = self._logger.get_summary()
        print('initial: {0}, after {2} years, total now: {1}, cagr: {3}'.format(initial_total, total, years, cagr))
        self._logger.save()

    def _trade(self, signals, day):
        self._portfolio.update_current_price(day)
        for signal in signals:
            if signal.status == 2:
                trade_data = self._data_engine.get_trade_data_by_date(signal.ts_code, day)
                suggest_position_size = self._risk_controller.evaluate_max_position_size(signal.ts_code, trade_data)
                suggest_position_size = suggest_position_size if suggest_position_size <= self._max_position_size else self._max_position_size
                print(signal, suggest_position_size)
                self._portfolio.buy(signal.ts_code, self._get_close_price(signal.ts_code),
                                    position_size=suggest_position_size, position_control=self._position_control,
                                    hold_date=day)
            elif signal.status == 0:
                print(signal)
                self._portfolio.sell(signal.ts_code)
        self._portfolio.update_current_price(day)

    def _get_close_price(self, ts_code):
        return self._data_engine.get_stock_price_on_date(ts_code, self._today)
