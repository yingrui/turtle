from engine.policy.Policy import Policy
from engine.policy.Signal import Signal


class AtrPolicy(Policy):

    def __init__(self, ts_code, trade_data, parameters={}):
        Policy.__init__(self, ts_code, trade_data)
        self._ma_days = parameters.get('trade_policy.atr.ma_days', 70)
        self._atr_days = parameters.get('trade_policy.atr.atr_days', 20)
        self._up = parameters.get('trade_policy.atr.up', 7)
        self._down = parameters.get('trade_policy.atr.down', 3)

    def analysis(self) -> Signal:
        if self._trade_data.shape[0] <= 0:
            return Signal(self._ts_code, 'stay')

        time_series = self._trade_data.qfq
        sma = time_series.rolling(self._ma_days).mean()
        if sma.shape[0] < 1:
            return Signal(self._ts_code, 'stay')

        trade_data = self._trade_data
        daily_range = trade_data[['high', 'pre_close']].max(axis=1) - trade_data[['low', 'pre_close']].min(axis=1)
        average_true_range = daily_range.rolling(self._atr_days).mean()
        up = sma + average_true_range * self._up
        down = sma - average_true_range * self._down

        if time_series.iloc[-1] >= up.iloc[-1]:
            return Signal(self._ts_code, 'buy')

        if time_series.iloc[-1] < down.iloc[-1]:
            return Signal(self._ts_code, 'sell')

        return Signal(self._ts_code, 'stay')
