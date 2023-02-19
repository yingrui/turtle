from engine.policy.Policy import Policy
from engine.policy.Signal import Signal


class BollingPolicy(Policy):

    def __init__(self, ts_code, trade_data, parameters={}):
        Policy.__init__(self, ts_code, trade_data)
        self._ma_days = parameters.get('trade_policy.bolling.ma_days', 70)
        self._up = parameters.get('trade_policy.bolling.up', 2.5)
        self._down = parameters.get('trade_policy.bolling.down', 2.5)

    def analysis(self) -> Signal:
        if self._trade_data.shape[0] <= 0:
            return Signal(self._ts_code, 'stay')

        time_series = self._trade_data.qfq
        sma = time_series.rolling(self._ma_days).mean()
        if sma.shape[0] < 1:
            return Signal(self._ts_code, 'stay')

        std = time_series.rolling(self._ma_days).std()
        up = sma + std * self._up
        down = sma - std * self._down

        if time_series.iloc[-1] >= up.iloc[-1]:
            return Signal(self._ts_code, 'buy')

        if time_series.iloc[-1] < down.iloc[-1]:
            return Signal(self._ts_code, 'sell')

        return Signal(self._ts_code, 'stay')
