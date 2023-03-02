from engine.policy.Policy import Policy
from engine.policy.Signal import Signal


class SimpleMovingAveragePolicy(Policy):

    def __init__(self, ts_code, trade_data, parameters={}):
        Policy.__init__(self, ts_code, trade_data)
        self._window_1 = parameters.get('trade_policy.moving_average.window_1', 20)
        self._window_2 = parameters.get('trade_policy.moving_average.window_2', 70)
        self._window_3 = parameters.get('trade_policy.moving_average.window_3', 150)
        self._is_triple = parameters.get('trade_policy.moving_average.triple', False)
        self._should_check_price = parameters.get('trade_policy.moving_average.should_price_higher_than_ma', False)

    def analysis(self) -> Signal:
        if self._trade_data.shape[0] <= 0:
            return Signal(self._ts_code, 'stay')

        time_series = self._trade_data.qfq
        sma_1 = time_series.rolling(self._window_1).mean()
        sma_2 = time_series.rolling(self._window_2).mean()
        is_price_higher_than_ma = time_series.iloc[-1] > sma_2.iloc[-1] if self._should_check_price else True
        is_trend_up = False
        is_trend_down = False
        if self._is_triple:
            sma_3 = time_series.rolling(self._window_3).mean()
            is_trend_up = sma_1.iloc[-1] > sma_3.iloc[-1] and sma_2.iloc[-1] > sma_3.iloc[-1]
            is_trend_down = sma_3.iloc[-1] > sma_1.iloc[-1] and sma_3.iloc[-1] > sma_2.iloc[-1]

        if sma_2.shape[0] < 2:
            return Signal(self._ts_code, 'stay')

        today = 1 if (sma_1.iloc[-1] - sma_2.iloc[-1]) > 0 else -1
        yesterday = 1 if (sma_1.iloc[-2] - sma_2.iloc[-2]) > 0 else -1
        if today > yesterday and not is_trend_down and is_price_higher_than_ma:
            return Signal(self._ts_code, 'buy')
        elif today < yesterday and not is_trend_up:
            return Signal(self._ts_code, 'sell')
        else:
            return Signal(self._ts_code, 'stay')
