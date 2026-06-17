import math

import pandas as pd

from app.core.engine.Trend import Trend


class TrendAnalyzer:

    def __init__(self, ts_code, trade_data, parameters={}):
        self._ts_code = ts_code
        self._trade_data = trade_data
        self._window_1 = parameters.get('portfolio_filter.trend.moving_average.window_1', 20)
        self._window_2 = parameters.get('portfolio_filter.trend.moving_average.window_2', 70)
        self._window_3 = parameters.get('portfolio_filter.trend.moving_average.window_3', 150)

    @staticmethod
    def _percentage_normalize(time_series):
        mean = time_series.mean()
        if mean is None or pd.isna(mean) or mean == 0:
            return time_series * 0
        return (time_series - mean) / mean

    @staticmethod
    def _zero_normalize(time_series):
        std = time_series.std()
        if std is None or pd.isna(std) or std == 0:
            return time_series * 0
        return (time_series - time_series.mean()) / std

    @staticmethod
    def _safe_float(v) -> float:
        if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
            return 0.0
        return float(v)

    def analysis_trend(self) -> Trend:
        bar_count = self._trade_data.shape[0]
        if bar_count <= self._window_3:
            return Trend(
                self._ts_code,
                'unknown',
                reason='insufficient_history',
            )

        time_series = self._trade_data.qfq
        std = self._safe_float(self._percentage_normalize(time_series.tail(60)).std())

        sma_1 = time_series.rolling(self._window_1).mean()
        sma_2 = time_series.rolling(self._window_2).mean()
        sma_3 = time_series.rolling(self._window_3).mean()

        ma1 = sma_1.iloc[-1]
        ma2 = sma_2.iloc[-1]
        ma3 = sma_3.iloc[-1]
        close = time_series.iloc[-1]

        if any(pd.isna(v) for v in (ma1, ma2, ma3, close)):
            return Trend(self._ts_code, 'unknown', stationary=std, reason='invalid_ma')

        gradient = 0.0
        if sma_3.shape[0] >= 5:
            days = 30 if sma_3.shape[0] >= 30 else sma_3.shape[0]
            sma_norm = self._zero_normalize(sma_3.tail(days))
            gradient = self._safe_float((sma_norm.iloc[-1] - sma_norm.iloc[-days]) / days)

        # Strong: full MA stack alignment (original rule)
        if ma1 > ma2 > ma3:
            return Trend(self._ts_code, 'up', gradient=gradient, stationary=std, reason='strong_up')
        if ma1 < ma2 < ma3:
            return Trend(self._ts_code, 'down', gradient=gradient, stationary=std, reason='strong_down')

        # Relaxed: short/medium MA + price vs long MA
        if ma1 > ma2 and close > ma3:
            return Trend(self._ts_code, 'up', gradient=gradient, stationary=std, reason='weak_up')
        if ma1 < ma2 and close < ma3:
            return Trend(self._ts_code, 'down', gradient=gradient, stationary=std, reason='weak_down')

        return Trend(self._ts_code, 'unknown', gradient=gradient, stationary=std, reason='sideways')
