import datetime
from datetime import date
from unittest import TestCase

from engine.StockTradeDataEngine import StockTradeDataEngine
from engine.TrendAnalyzer import TrendAnalyzer


class TestTrendAnalyzer(TestCase):

    def test_detect_up_trend(self):
        parameters = {
            'portfolio_filter.basic.ignore_st': True,
            'portfolio_filter.trend.moving_average.window_1': 50,
            'portfolio_filter.trend.moving_average.window_2': 150,
            'portfolio_filter.trend.moving_average.window_3': 250,
        }

        data_engine = StockTradeDataEngine()
        current_date = date(2017, 1, 1)
        # ts_code = '600519.SH'
        ts_code = '600143.SH'
        start_date = current_date - datetime.timedelta(days=2 * 365)
        trade_data = data_engine.get_trade_data_by_code(ts_code, start_date, current_date)

        trend_analyzer = TrendAnalyzer(ts_code=ts_code, trade_data=trade_data, parameters=parameters)
        trend = trend_analyzer.analysis_trend()
        print(trend)
        self.assertEqual('up', trend.status)

