from engine.Signal import Signal


class SimpleMovingAveragePolicy:

    def __init__(self, ts_code, trade_data, parameters={}):
        self._ts_code = ts_code
        self._trade_data = trade_data
        self._window_1 = parameters.get('trade_policy.moving_average.window_1', 20)
        self._window_2 = parameters.get('trade_policy.moving_average.window_2', 70)

    def analysis(self):
        if self._trade_data.shape[0] <= 0:
            return Signal(self._ts_code, 1)

        time_series = self._trade_data.close
        sma_1 = time_series.rolling(self._window_1).mean()
        sma_2 = time_series.rolling(self._window_2).mean()
        if sma_2.shape[0] < 2:
            return Signal(self._ts_code, 1)

        today = 1 if (sma_1.iloc[-1] - sma_2.iloc[-1]) > 0 else -1
        yesterday = 1 if (sma_1.iloc[-2] - sma_2.iloc[-2]) > 0 else -1
        if today > yesterday:
            return Signal(self._ts_code, 2)
        elif today < yesterday:
            return Signal(self._ts_code, 0)
        else:
            return Signal(self._ts_code, 1)

