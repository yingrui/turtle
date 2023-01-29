from unittest import TestCase
from datetime import date

import pandas as pd

from engine.Portfolio import Portfolio
from engine.StockTradeDataEngine import StockTradeDataEngine


class TestPortfolio(TestCase):

    def test_invest_new_stock(self):
        ts_code = '600519.sh'
        portfolio = self._mock_empty_portfolio()
        shares, msg = portfolio.buy(ts_code=ts_code, price=1800)
        self.assertEqual(100, shares)
        self.assertEqual('Success', msg)
        self.assertEqual(0, portfolio.benefit)
        self.assertEqual(1, len(portfolio.investments))
        self.assertEqual(0, portfolio.get_investment(ts_code).benefit)

    def test_invest_new_stock_with_specify_shares(self):
        ts_code = '600519.sh'
        portfolio = self._mock_empty_portfolio(balance=400000)
        shares, msg = portfolio.buy(ts_code=ts_code, price=1800, max_lots_of_stock=5)
        self.assertEqual(200, shares)
        self.assertEqual('Success', msg)
        self.assertEqual(0, portfolio.benefit)
        self.assertEqual(1, len(portfolio.investments))
        self.assertEqual(0, portfolio.get_investment(ts_code).benefit)

    def test_invest_new_stock_with_stock_control(self):
        ts_code = '600519.sh'
        portfolio = self._mock_empty_portfolio(balance=400000)
        shares, msg = portfolio.buy(ts_code=ts_code, price=800, max_lots_of_stock=5, position_control=0.6)
        self.assertEqual(300, shares)
        self.assertEqual('Success', msg)
        self.assertEqual(0, portfolio.benefit)
        self.assertEqual(1, len(portfolio.investments))
        self.assertEqual(0, portfolio.get_investment(ts_code).benefit)

    def test_invest_but_with_insufficient_balance(self):
        portfolio = self._mock_portfolio_with_100_shares_of_600519()
        shares, msg = portfolio.buy(ts_code='600519.sh', price=1800)
        self.assertEqual(0, shares)
        self.assertEqual('Insufficient balance', msg)

    def test_merge_investments_with_same_code(self):
        ts_code = '600519.sh'
        portfolio = self._mock_empty_portfolio(balance=400000)
        # buy 100 shares
        portfolio.buy(ts_code=ts_code, price=1800)

        # the price is 1900 now.
        portfolio.update_current_price(self._mock_stock_trade_data(ts_code.upper(), 1900))
        self.assertEqual(410000, portfolio.total)
        self.assertEqual(220000, portfolio.balance)

        # buy another 100 shares
        shares, msg = portfolio.buy(ts_code=ts_code, price=1900)
        self.assertEqual(100, shares)
        self.assertEqual('Success', msg)

        self.assertEqual(410000, portfolio.total)
        self.assertEqual(30000, portfolio.balance)
        self.assertEqual(1, len(portfolio.investments))
        self.assertEqual(10000, portfolio.get_investment(ts_code).benefit)
        self.assertEqual(1850, portfolio.get_investment(ts_code).buy_price)
        self.assertEqual(1900, portfolio.get_investment(ts_code).current_price)

    def test_sold_out_100_shares(self):
        portfolio = self._mock_portfolio_with_100_shares_of_600519()

        portfolio.update_current_price(StockTradeDataEngine().get_trade_data_on_date(date(2023, 1, 20)))
        self.assertEqual(1860.01, portfolio.investments[0].current_price)

        sell_shares, benefit = portfolio.sell(ts_code='600519.sh')
        self.assertEqual(100, sell_shares)
        self.assertEqual(6001, benefit)

        self.assertEqual(6001, portfolio.benefit)
        self.assertEqual(206001, portfolio.total)
        self.assertEqual(206001, portfolio.balance)
        self.assertEqual(0, len(portfolio.investments))

    def _mock_empty_portfolio(self, balance=200000):
        return Portfolio('mock', [], balance, 0, balance)

    def _mock_portfolio_with_100_shares_of_600519(self):
        portfolio = self._mock_empty_portfolio()
        portfolio.buy(ts_code='600519.sh', price=1800)
        return portfolio

    def _mock_portfolio_with_200_shares_of_600519(self):
        portfolio = self._mock_empty_portfolio(balance=400000)
        portfolio.buy(ts_code='600519.sh', price=1800)
        portfolio.buy(ts_code='600519.sh', price=1800)
        return portfolio

    @staticmethod
    def _mock_stock_trade_data(ts_code, price):
        return pd.DataFrame({'ts_code': [ts_code], 'close': [price]})
