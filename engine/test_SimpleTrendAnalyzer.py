import datetime
from datetime import date
from unittest import TestCase

from engine.StockTradeDataEngine import StockTradeDataEngine
from engine.TrendAnalyzer import TrendAnalyzer


class TestTrendAnalyzer(TestCase):
    @property
    def parameters(self):
        return {
            'portfolio_filter.basic.ignore_st': True,
            'portfolio_filter.trend.moving_average.window_1': 50,
            'portfolio_filter.trend.moving_average.window_2': 150,
            'portfolio_filter.trend.moving_average.window_3': 250,
        }

    def test_detect_up_trend(self):
        ts_code = '600519.SH'
        current_date = date(2017, 1, 1)
        start_date = current_date - datetime.timedelta(days=2 * 365)
        trade_data = StockTradeDataEngine().get_trade_data_by_code(ts_code, start_date, current_date)

        trend_analyzer = TrendAnalyzer(ts_code=ts_code, trade_data=trade_data, parameters=self.parameters)
        trend = trend_analyzer.analysis_trend()
        print(trend)
        self.assertEqual('up', trend.status)
        self.assertEqual(0.1078, round(trend.gradient, 4))
        self.assertEqual(0.0224, round(trend.stationary, 4))

    def test_trend_with_negative_gradient(self):
        ts_code = '000710.SZ'
        current_date = date(2017, 1, 1)
        start_date = current_date - datetime.timedelta(days=2 * 365)
        trade_data = StockTradeDataEngine().get_trade_data_by_code(ts_code, start_date, current_date)

        trend_analyzer = TrendAnalyzer(ts_code=ts_code, trade_data=trade_data, parameters=self.parameters)
        trend = trend_analyzer.analysis_trend()
        print(trend)
        self.assertEqual(0.1582, round(trend.gradient, 4))
