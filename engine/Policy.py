from engine.Signal import Signal


class SimpleMovingAveragePolicy:

    def __init__(self, ts_code, trade_data):
        self._ts_code = ts_code
        self._trade_data = trade_data

    def analysis(self):
        if self._trade_data.shape[0] <= 0:
            return Signal(self._ts_code, 1)

        time_series = self._trade_data.close
        sma_20 = time_series.rolling(20).mean()
        sma_70 = time_series.rolling(70).mean()
        if sma_70.shape[0] < 20:
            return Signal(self._ts_code, 1)

        today = 1 if (sma_20.iloc[-1] - sma_70.iloc[-1]) > 0 else -1
        yesterday = 1 if (sma_20.iloc[-2] - sma_70.iloc[-2]) > 0 else -1
        if today > yesterday:
            return Signal(self._ts_code, 2)
        elif today < yesterday:
            return Signal(self._ts_code, 0)
        else:
            return Signal(self._ts_code, 1)

