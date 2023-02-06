from datetime import date
from unittest import TestCase

from engine.StockTradeDataEngine import StockTradeDataEngine


class TestStockTradeDataEngine(TestCase):

    def test_list_stocks_on_date(self):
        data_engine = StockTradeDataEngine()
        stocks = data_engine.list_stocks_on_date(date(2020, 1, 1))
        self.assertEqual(3681, stocks.shape[0])
