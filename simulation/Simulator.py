import pandas as pd

from engine import Portfolio, TradeSignalMonitor
from engine.InvestmentLogger import InvestmentLogger
from engine.RiskController import RiskController
from engine.StockTradeDataEngine import StockTradeDataEngine
from util.math_methods import round_down


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
        self._should_check_stop_loss_point = parameters.get('risk_control.stop_loss_point.should_check', False)
        self._n_times_atr_for_stop_loss_point = parameters.get('risk_control.stop_loss_point.n_times_atr', 2)

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
        if self._should_check_stop_loss_point:
            self._check_stop_loss_point()
        self._trade_on_signals(day, signals)
        self._portfolio.update_current_price(day)

    def _trade_on_signals(self, day, signals):
        for signal in signals:
            if signal.status == 2:
                trade_data = self._data_engine.get_trade_data_by_date(signal.ts_code, day)
                position_size, atr = self._risk_controller.evaluate_buying_position_size(signal.ts_code, trade_data)
                if position_size > self._max_position_size:
                    position_size = self._max_position_size
                price = self._get_close_price(signal.ts_code)
                stop_loss_point = round_down(price - self._n_times_atr_for_stop_loss_point * atr)
                print(signal, position_size, price, stop_loss_point)
                self._portfolio.buy(signal.ts_code, price=price, position_size=position_size,
                                    position_control=self._position_control,
                                    hold_date=day, stop_loss_point=stop_loss_point)
            elif signal.status == 0:
                print(signal)
                self._portfolio.sell(signal.ts_code)

    def _check_stop_loss_point(self):
        for investment in self._portfolio.investments:
            price = self._get_close_price(investment.ts_code)
            if price <= investment.stop_loss_point:
                print('sell {0}, due to reach the stop loss point'.format(investment.ts_code))
                self._portfolio.sell(investment.ts_code)

    def _get_close_price(self, ts_code):
        return self._data_engine.get_stock_price_on_date(ts_code, self._today)
