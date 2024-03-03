from engine.policy.Policy import Policy
from engine.policy.Signal import Signal


class DonchianPolicy(Policy):

    def __init__(self, ts_code, trade_data, parameters={}):
        Policy.__init__(self, ts_code, trade_data)
        self._window_1 = parameters.get('trade_policy.donchian.ma_window_1', 20)
        self._window_2 = parameters.get('trade_policy.donchian.ma_window_2', 70)
        self._up_days = parameters.get('trade_policy.donchian.up_days', 20)
        self._down_days = parameters.get('trade_policy.donchian.down_days', 10)

    def analysis(self) -> Signal:
        if self._trade_data.shape[0] <= 0:
            return Signal(self._ts_code, 'stay')

        time_series = self._trade_data.qfq
        sma_1 = time_series.rolling(self._window_1).mean()
        sma_2 = time_series.rolling(self._window_2).mean()
        if sma_2.shape[0] < 2:
            return Signal(self._ts_code, 'stay')

        is_trend_up = sma_1.iloc[-1] > sma_2.iloc[-1]
        is_trend_down = sma_1.iloc[-1] < sma_2.iloc[-1]

        max_in_previous_days = time_series.rolling(self._up_days).max()
        min_in_previous_days = time_series.rolling(self._down_days).min()
        if time_series.iloc[-1] > max_in_previous_days.iloc[-2] and not is_trend_down:
            return Signal(self._ts_code, 'buy')

        if time_series.iloc[-1] < min_in_previous_days.iloc[-2] and not is_trend_up:
            return Signal(self._ts_code, 'sell')

        return Signal(self._ts_code, 'stay')

