from datetime import date
from unittest import TestCase

from app.core.engine.StockTradeDataEngine import StockTradeDataEngine


class TestStockTradeDataEngine(TestCase):

    def test_list_stocks_on_date(self):
        data_engine = StockTradeDataEngine()
        stocks = data_engine.list_stocks_on_date(date(2020, 1, 1))
        # All four fixture stocks are listed before 2020-01-01.
        self.assertEqual(4, stocks.shape[0])
