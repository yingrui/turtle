import datetime

from util.math_methods import round_down


class RiskController:

    def __init__(self, portfolio=None, data_engine=None, parameters={}, logger=None):
        self._portfolio = portfolio
        self._data_engine = data_engine
        self._logger = logger
        self._bearable_trading_loss = parameters.get('bearable_trading_loss', 0.01)
        self._position_control = parameters.get('position_control', 1)
        self._reserve_profit = parameters.get('position_control.reserve_profit', 0)
        self._max_position_size = parameters.get('max_position_size', 10)
        self._max_position_ratio = parameters.get('max_position_ratio', 0.5)
        self._should_check_stop_loss_point = parameters.get('stop_loss_point.should_check', False)
        self._should_update_stop_loss_point = parameters.get('stop_loss_point.should_update', False)
        self._keep_profit = parameters.get('stop_loss_point.keep_profit', 0.1)
        self._n_times_atr_for_stop_loss_point = parameters.get('stop_loss_point.n_times_atr', 2)
        self._should_check_max_holding_period = parameters.get('max_holding_period.should_check', False)
        self._max_holding_period = parameters.get('max_holding_period.days', 80)

    def evaluate_buying_position_size(self, ts_code, trade_data):
        daily_range = trade_data[['high', 'pre_close']].max(axis=1) - trade_data[['low', 'pre_close']].min(axis=1)
        average_true_range = daily_range.rolling(20).mean()
        atr = round_down(average_true_range.values[-1])
        position_size = int((self._portfolio.total * self._bearable_trading_loss) / atr / 100)
        price = trade_data.close.values[-1]
        while position_size * 100 * price > self._portfolio.total * self._max_position_ratio:
            position_size = position_size - 1
        return position_size, atr

    @property
    def position_control(self):
        profit = self._portfolio.total - self._portfolio.initial_investment
        return self._position_control - max(0, profit) * self._reserve_profit / max(1, self._portfolio.total)

    @property
    def max_position_size(self):
        return self._max_position_size

    def stop_loss_point(self, price, atr):
        return round_down(price - self._n_times_atr_for_stop_loss_point * atr)

    def execute_risk_control(self, today):
        if self._should_check_stop_loss_point:
            self._check_stop_loss_point(today)
        if self._should_check_max_holding_period:
            self._check_max_holding_period(today)

    def _check_stop_loss_point(self, today):
        for investment in self._portfolio.investments:
            yesterday = today + datetime.timedelta(days=-1)
            yesterday_price, y_h, y_l = self._data_engine.get_stock_price_on_date(investment.ts_code, yesterday)
            price, high, low = self._data_engine.get_stock_price_on_date(investment.ts_code, today)
            if yesterday_price <= investment.stop_loss_point:
                reach_stop_loss_point_message = '{0}| RiskController: sell {1}, due to reach the stop loss point'
                self._logger.log(reach_stop_loss_point_message.format(today.strftime('%Y-%m-%d'), investment.ts_code))
                self._logger.log_sell_action(self._portfolio.get_stock(investment.ts_code), today, 'stop loss point')
                self._portfolio.sell(investment.ts_code)
            elif self._should_update_stop_loss_point:
                increased_price = price - investment.buy_price
                increased_ratio = increased_price / investment.buy_price
                new_stop_loss_point = investment.buy_price + increased_price * self._keep_profit
                if increased_ratio > 0.1 and new_stop_loss_point > investment.stop_loss_point:
                    investment.set_stop_loss_point(new_stop_loss_point)

    def _check_max_holding_period(self, today):
        for investment in self._portfolio.investments:
            hold_date = investment.hold_date
            if (today - hold_date).days > self._max_holding_period:
                max_holding_period_message = '{0}| RiskController: sell {1}, due to reach the max holding period'
                self._logger.log(max_holding_period_message.format(today.strftime('%Y-%m-%d'), investment.ts_code))
                self._logger.log_sell_action(self._portfolio.get_stock(investment.ts_code), today, 'hold period limit')
                self._portfolio.sell(investment.ts_code)
