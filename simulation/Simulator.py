import pandas as pd

from engine.InvestmentLogger import InvestmentLogger
from engine.RiskController import RiskController
from engine.TradeSignalMonitor import TradeSignalMonitor


class Simulator:

    def __init__(self, portfolio, follow_stocks, data_engine, risk_control):
        self._risk_controller = None
        self._trade_monitor = None
        self._today = None
        self._portfolio = portfolio
        self._data_engine = data_engine
        self._logger = InvestmentLogger(portfolio.name, folder='logs')
        self._follow_stocks = follow_stocks
        self._risk_controller = RiskController(self._portfolio, self._data_engine, risk_control, self._logger)

    def set_policy(self, parameters):
        self._trade_monitor = TradeSignalMonitor(self._data_engine, self._follow_stocks, parameters)

    def run(self, start_date, end_date):
        self._logger.log('----- start')
        signals = []
        for day in pd.date_range(start=start_date, end=end_date):
            if self._data_engine.is_trade_day(day):
                self._today = day
                self._portfolio.adjust_holding_shares(day)
                self._trade(signals, day)
                self._logger.log_portfolio(portfolio=self._portfolio, current_date=day)
                self._logger.log('{0}| {1}'.format(day.strftime('%Y-%m-%d'), self._portfolio))
                signals = self.detect_signals(day)
        self._logger.log_holding_shares(self._portfolio, day)
        self._logger.save()
        print('{0}| {1}'.format(day.strftime('%Y-%m-%d'), self._portfolio))

    def detect_signals(self, day):
        signals = self._trade_monitor.detect_signals(day)
        for signal in signals:
            if signal.status == 'sell':
                self._logger.log('{0}| detected signal: {1}'.format(day.strftime('%Y-%m-%d'), signal))
            if signal.status == 'buy':
                position_size, price, stop_loss_point = self._evaluate_position(day, signal)
                self._logger.log('{0}| detected signal: {1} {2} {3} {4}'.format(
                    day.strftime('%Y-%m-%d'), signal, position_size, price, stop_loss_point))

        return signals

    def _evaluate_position(self, day, signal):
        trade_data = self._data_engine.get_trade_data_by_date(signal.ts_code, day)
        position_size, atr = self._risk_controller.evaluate_buying_position_size(signal.ts_code, trade_data)
        if position_size > self._risk_controller.max_position_size:
            position_size = self._risk_controller.max_position_size
        price, high, low = self._get_close_price(signal.ts_code)
        stop_loss_point = self._risk_controller.stop_loss_point(price, atr)
        return position_size, price, stop_loss_point

    def print_summary(self):
        self._logger.log('{0}'.format(self._portfolio))
        # initial_total, total, years, cagr = self._logger.get_summary()
        # print('initial: {0}, after {2} years, total now: {1}, cagr: {3}'.format(initial_total, total, years, cagr))

    def _trade(self, signals, day):
        self._risk_controller.execute_risk_control(day)
        self._trade_on_signals(day, signals)

        self._portfolio.update_current_price(day)

    def _trade_on_signals(self, day, signals):
        for signal in signals:
            if signal.status == 'buy':
                position_size, price, stop_loss_point = self._evaluate_position(day, signal)
                self._logger.log('{0}| {1} {2} {3} {4}'.format(day.strftime('%Y-%m-%d'), signal, position_size, price,
                                                               stop_loss_point))
                if not self._portfolio.has_stock(signal.ts_code):
                    self._portfolio.buy(signal.ts_code, price=price, position_size=position_size,
                                        position_control=self._risk_controller.position_control,
                                        hold_date=day, stop_loss_point=stop_loss_point)
            elif signal.status == 'sell':
                self._logger.log('{0}| {1}'.format(day.strftime('%Y-%m-%d'), signal))
                if self._portfolio.has_stock(signal.ts_code):
                    self._logger.log_sell_action(self._portfolio.get_stock(signal.ts_code), day, 'sell signal')
                    self._portfolio.sell(signal.ts_code)

    def _get_close_price(self, ts_code):
        return self._data_engine.get_stock_price_on_date(ts_code, self._today)
