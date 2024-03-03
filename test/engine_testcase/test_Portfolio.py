from datetime import date
from unittest import TestCase

from engine.Portfolio import Portfolio
from engine.StockTradeDataEngine import StockTradeDataEngine
from engine_testcase.StubPortfolio import StubPortfolio


class TestPortfolio(TestCase):

    def test_increase_investment(self):
        ts_code = '600519.sh'
        portfolio = StubPortfolio.empty_portfolio(balance=400000)
        shares, msg = portfolio.buy(ts_code=ts_code, price=1800, position_size=5, hold_date=date(2023, 1, 20))
        self.assertEqual(200, shares)
        self.assertEqual(40000, portfolio.balance)
        portfolio.increase_investment(100000)
        self.assertEqual(140000, portfolio.balance)
        self.assertEqual(500000, portfolio.total)

    def test_invest_new_stock(self):
        ts_code = '600519.sh'
        portfolio = StubPortfolio.empty_portfolio()
        shares, msg = portfolio.buy(ts_code=ts_code, price=1800, hold_date=date(2023, 1, 20))
        self.assertEqual(100, shares)
        self.assertEqual('Success', msg)
        self.assertEqual(0, portfolio.benefit)
        self.assertEqual(1, len(portfolio.investments))
        self.assertEqual(0, portfolio.get_investment(ts_code).benefit)
        self.assertEqual('2023-01-20', portfolio.get_investment(ts_code).hold_date.strftime('%Y-%m-%d'))

    def test_invest_new_stock_with_specify_shares(self):
        ts_code = '600519.sh'
        portfolio = StubPortfolio.empty_portfolio(balance=400000)
        shares, msg = portfolio.buy(ts_code=ts_code, price=1800, position_size=5, hold_date=date(2023, 1, 20))
        self.assertEqual(200, shares)
        self.assertEqual('Success', msg)
        self.assertEqual(0, portfolio.benefit)
        self.assertEqual(1, len(portfolio.investments))
        self.assertEqual(0, portfolio.get_investment(ts_code).benefit)

    def test_invest_new_stock_with_stock_control(self):
        ts_code = '600519.sh'
        portfolio = StubPortfolio.empty_portfolio(balance=400000)
        shares, msg = portfolio.buy(ts_code=ts_code, price=800, position_size=5, position_control=0.6,
                                    hold_date=date(2023, 1, 20))
        self.assertEqual(300, shares)
        self.assertEqual('Success', msg)
        self.assertEqual(0, portfolio.benefit)
        self.assertEqual(1, len(portfolio.investments))
        self.assertEqual(0, portfolio.get_investment(ts_code).benefit)

    def test_invest_but_with_insufficient_balance(self):
        portfolio = StubPortfolio.portfolio_with_100_shares_of_600519()
        shares, msg = portfolio.buy(ts_code='600519.sh', price=1800, hold_date=date(2023, 1, 20))
        self.assertEqual(0, shares)
        self.assertEqual('Insufficient balance', msg)

    def test_adjust_holding_shares(self):
        ts_code = '600519.sh'
        portfolio = StubPortfolio.empty_portfolio(balance=400000)
        # buy 100 shares
        portfolio.buy(ts_code=ts_code, price=2030, hold_date=date(2022, 6, 29))
        portfolio.adjust_holding_shares(date(2022, 6, 30))
        self.assertEqual(401500 + 2167.5, portfolio.total)
        self.assertEqual(2167.5, portfolio.benefit)
        self.assertEqual(400000 - 203000 + 2167.5, portfolio.balance)

    def test_merge_investments_with_same_code(self):
        ts_code = '600519.sh'
        portfolio = StubPortfolio.empty_portfolio(balance=400000)
        # buy 100 shares
        portfolio.buy(ts_code=ts_code, price=1800, hold_date=date(2023, 1, 20))

        # the price is 1900 now.
        portfolio.update_current_price(date(2023, 1, 20))
        self.assertEqual(406001, portfolio.total)
        self.assertEqual(220000, portfolio.balance)
        self.assertEqual('2023-01-20', portfolio.get_investment(ts_code).hold_date.strftime('%Y-%m-%d'))

        # buy another 100 shares
        shares, msg = portfolio.buy(ts_code=ts_code, price=1900, hold_date=date(2023, 1, 22))
        self.assertEqual(100, shares)
        self.assertEqual('Success', msg)

        self.assertEqual(406001, portfolio.total)
        self.assertEqual(30000, portfolio.balance)
        self.assertEqual(1, len(portfolio.investments))
        self.assertEqual(10000, portfolio.get_investment(ts_code).benefit)
        self.assertEqual(1850, portfolio.get_investment(ts_code).buy_price)
        self.assertEqual(1900, portfolio.get_investment(ts_code).current_price)
        self.assertEqual('2023-01-20', portfolio.get_investment(ts_code).hold_date.strftime('%Y-%m-%d'))

    def test_sold_out_100_shares(self):
        portfolio = StubPortfolio.portfolio_with_100_shares_of_600519()

        portfolio.update_current_price(date(2023, 1, 20))
        self.assertEqual(1860.01, portfolio.investments[0].current_price)

        sell_shares, benefit = portfolio.sell(ts_code='600519.sh')
        self.assertEqual(100, sell_shares)
        self.assertEqual(6001, benefit)

        self.assertEqual(6001, portfolio.benefit)
        self.assertEqual(206001, portfolio.total)
        self.assertEqual(206001, portfolio.balance)
        self.assertEqual(0, len(portfolio.investments))


