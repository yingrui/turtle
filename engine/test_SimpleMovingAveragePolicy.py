from datetime import date
from unittest import TestCase

from engine.Policy import SimpleMovingAveragePolicy
from engine.StockTradeDataEngine import StockTradeDataEngine


class TestSimpleMovingAveragePolicy(TestCase):
    def test_should_return_signal_of_do_nothing(self):
        ts_code = '600519.SH'
        df_trade_data = StockTradeDataEngine().get_trade_data_by_date(ts_code, date(2023, 1, 20), 200)

        policy = SimpleMovingAveragePolicy(ts_code, df_trade_data)

        signal = policy.analysis()
        self.assertEqual(1, signal.status)

    def test_should_return_signal_of_buy(self):
        ts_code = '600519.SH'
        df_trade_data = StockTradeDataEngine().get_trade_data_by_date(ts_code, date(2022, 12, 22), 200)

        policy = SimpleMovingAveragePolicy(ts_code, df_trade_data)

        signal = policy.analysis()
        self.assertEqual(2, signal.status)

    def test_should_return_signal_of_sell(self):
        ts_code = '600519.SH'
        df_trade_data = StockTradeDataEngine().get_trade_data_by_date(ts_code, date(2022, 8, 25), 200)

        policy = SimpleMovingAveragePolicy(ts_code, df_trade_data)

        signal = policy.analysis()
        self.assertEqual(0, signal.status)
