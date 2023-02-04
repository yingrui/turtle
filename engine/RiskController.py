class RiskController:

    def __init__(self, portfolio=None, parameters={}):
        self._portfolio = portfolio
        self._bearable_trading_loss = parameters.get('risk_control.bearable_trading_loss', 0.01)

    def evaluate_max_position_size(self, ts_code, trade_data):
        daily_range = trade_data.high - trade_data.low
        average_true_range = daily_range.rolling(20).mean()
        atr = average_true_range.values[-1]
        position_size = int((self._portfolio.total * self._bearable_trading_loss) / atr / 100)
        return position_size
