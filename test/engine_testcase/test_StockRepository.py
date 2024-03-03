from datetime import date
from unittest import TestCase

from engine.StockRepository import StockRepository


class TestStockIterator(TestCase):
    def test_find_stock_by_code(self):
        stock_repo = StockRepository()
        stock = stock_repo.find_stock_by_code('600519.sh')
        self.assertIsNotNone(stock, 'Stock is None, please check data')
        self.assertEqual('600519', stock.symbol)
        self.assertEqual('贵州茅台', stock.name)
        self.assertEqual('贵州', stock.area)
        self.assertEqual('白酒', stock.industry)
        self.assertEqual('主板', stock.market)
        self.assertEqual('Listed', stock.status)
        self.assertEqual(date(2001, 8, 27), stock.list_date)

    def test_find_stock_by_name(self):
        stock_repo = StockRepository()
        stock = stock_repo.find_stock_by_name('茅台')
        self.assertIsNotNone(stock, 'Stock is None, please check data')
        self.assertEqual('600519.SH', stock.ts_code)
        self.assertEqual('600519', stock.symbol)
        self.assertEqual('贵州茅台', stock.name)
        self.assertEqual('贵州', stock.area)
        self.assertEqual('白酒', stock.industry)
        self.assertEqual('主板', stock.market)
        self.assertEqual('Listed', stock.status)
        self.assertEqual(date(2001, 8, 27), stock.list_date)

    def test_find_stock(self):
        stock_repo = StockRepository()
        stock = stock_repo.find_stock('茅台')
        self.assertIsNotNone(stock, 'Stock is None, please check data')
        self.assertEqual('600519.SH', stock.ts_code)
        self.assertEqual('600519', stock.symbol)
        self.assertEqual('贵州茅台', stock.name)
        self.assertEqual('贵州', stock.area)
        self.assertEqual('白酒', stock.industry)
        self.assertEqual('主板', stock.market)
        self.assertEqual('Listed', stock.status)
        self.assertEqual(date(2001, 8, 27), stock.list_date)
        stock = stock_repo.find_stock(stock.ts_code)
        self.assertIsNotNone(stock, 'Stock is None, please check data')
        self.assertEqual('600519.SH', stock.ts_code)

    def test_find_stocks_by_industry(self):
        stock_repo = StockRepository()
        stocks = stock_repo.find_stocks_by_industry('白酒')
        self.assertIsNotNone(stocks, 'Stock is None, please check data')
        self.assertGreater(len(stocks), 0)

    def test_find_all_stocks(self):
        stock_repo = StockRepository()
        stocks = stock_repo.find_all_stocks()
        self.assertIsNotNone(stocks, 'Stock is None, please check data')
        self.assertGreater(len(stocks), 0)
