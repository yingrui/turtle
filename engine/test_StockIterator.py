from datetime import date
from unittest import TestCase

from engine.StockIterator import StockIterator


class TestStockIterator(TestCase):
    def test_find_stocks_by_code(self):
        iterator = StockIterator()
        stock = iterator.find_stocks_by_code('600519.sh')
        self.assertIsNotNone(stock, 'Stock is None, please check data')
        self.assertEqual(stock.symbol, '600519')
        self.assertEqual(stock.name, '贵州茅台')
        self.assertEqual(stock.area, '贵州')
        self.assertEqual(stock.industry, '白酒')
        self.assertEqual(stock.market, '主板')
        self.assertEqual(stock.status, 'Listed')
        self.assertEqual(stock.list_date, date(2001, 8, 27))

    def test_find_stocks_by_industry(self):
        iterator = StockIterator()
        stocks = iterator.find_stocks_by_industry('白酒')
        self.assertIsNotNone(stocks, 'Stock is None, please check data')
        self.assertGreater(len(stocks), 0)

    def test_find_all_stocks(self):
        iterator = StockIterator()
        stocks = iterator.find_all_stocks()
        self.assertIsNotNone(stocks, 'Stock is None, please check data')
        self.assertGreater(len(stocks), 0)
