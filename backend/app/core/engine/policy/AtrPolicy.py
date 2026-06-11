from app.core.engine.policy.Policy import Policy
from app.core.engine.policy.Signal import Signal


class AtrPolicy(Policy):

    def __init__(self, ts_code, trade_data, parameters={}):
        Policy.__init__(self, ts_code, trade_data)
        self._ma_days = parameters.get('trade_policy.atr.ma_days', 70)
        self._atr_days = parameters.get('trade_policy.atr.atr_days', 20)
        self._up = parameters.get('trade_policy.atr.up', 7)
        self._down = parameters.get('trade_policy.atr.down', 3)

    def analysis(self) -> Signal:
        # If there is no trade data, stay
        if self._trade_data.shape[0] <= 0:
            return Signal(self._ts_code, 'stay')

        # Calculate moving average and ATR (Average True Range)
        moving_avg = self._trade_data['close'].rolling(window=self._ma_days).mean()




















