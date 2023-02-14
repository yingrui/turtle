from util.math_methods import round_down


class RiskController:

    def __init__(self, portfolio=None, data_engine=None, parameters={}):
        self._portfolio = portfolio
        self._data_engine = data_engine
        self._bearable_trading_loss = parameters.get('risk_control.bearable_trading_loss', 0.01)
        self._position_control = parameters.get('risk_control.position_control', 1)
        self._reserve_profit = parameters.get('risk_control.position_control.reserve_profit', 0)
        self._max_position_size = parameters.get('risk_control.max_position_size', 10)
        self._should_check_stop_loss_point = parameters.get('risk_control.stop_loss_point.should_check', False)
        self._n_times_atr_for_stop_loss_point = parameters.get('risk_control.stop_loss_point.n_times_atr', 2)
        self._should_check_max_holding_period = parameters.get('risk_control.max_holding_period.should_check', False)
        self._max_holding_period = parameters.get('risk_control.max_holding_period.days', 80)

    def evaluate_buying_position_size(self, ts_code, trade_data):
        daily_range = trade_data.high - trade_data.low
        average_true_range = daily_range.rolling(20).mean()
        atr = round_down(average_true_range.values[-1])
        position_size = int((self._portfolio.total * self._bearable_trading_loss) / atr / 100)
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
            price = self._data_engine.get_stock_price_on_date(investment.ts_code, today)
            if price <= investment.stop_loss_point:
                print('sell {0}, due to reach the stop loss point'.format(investment.ts_code))
                self._portfolio.sell(investment.ts_code)

    def _check_max_holding_period(self, today):
        for investment in self._portfolio.investments:
            hold_date = investment.hold_date
            if (today - hold_date).days > self._max_holding_period:
                print('sell {0}, due to reach the max holding period'.format(investment.ts_code))
                self._portfolio.sell(investment.ts_code)
