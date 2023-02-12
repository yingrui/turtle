from engine.Trend import Trend


class TrendAnalyzer:

    def __init__(self, ts_code, trade_data, parameters={}):
        self._ts_code = ts_code
        self._trade_data = trade_data
        self._window_1 = parameters.get('portfolio_filter.trend.moving_average.window_1', 20)
        self._window_2 = parameters.get('portfolio_filter.trend.moving_average.window_2', 70)
        self._window_3 = parameters.get('portfolio_filter.trend.moving_average.window_3', 150)

    @staticmethod
    def _max_min_normalize(time_series):
        return (time_series - time_series.min()) / (time_series.max() - time_series.min())

    @staticmethod
    def _zero_normalize(time_series):
        return (time_series - time_series.mean()) / time_series.std()

    @staticmethod
    def _percentage_normalize(time_series):
        return (time_series - time_series.mean()) / time_series.mean()

    def analysis_trend(self):
        if self._trade_data.shape[0] <= self._window_3:
            return Trend(self._ts_code, 'unknown')

        time_series = self._trade_data.qfq
        std = self._percentage_normalize(time_series.tail(60)).std()

        sma_1 = time_series.rolling(self._window_1).mean()
        sma_2 = time_series.rolling(self._window_2).mean()
        sma_3 = time_series.rolling(self._window_3).mean()

        if sma_3.shape[0] < 1:
            return Trend(self._ts_code, 'unknown')

        gradient = 0
        if sma_3.shape[0] >= 5:
            days = 30 if sma_3.shape[0] >= 30 else sma_3.shape[0]
            sma = self._zero_normalize(sma_3.tail(days))
            gradient = (sma.iloc[-1] - sma.iloc[-days]) / days

        if (sma_1.iloc[-1] - sma_3.iloc[-1]) > 0 and (sma_2.iloc[-1] - sma_3.iloc[-1]) > 0:
            return Trend(self._ts_code, 'up', gradient=gradient, stationary=std)

        if (sma_1.iloc[-1] - sma_3.iloc[-1]) < 0 and (sma_2.iloc[-1] - sma_3.iloc[-1]) < 0:
            return Trend(self._ts_code, 'down', gradient=gradient, stationary=std)

        return Trend(self._ts_code, 'unknown', gradient=gradient, stationary=std)
