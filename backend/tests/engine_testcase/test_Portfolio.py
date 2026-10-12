from datetime import date
from unittest import TestCase

from app.core.engine.Portfolio import Portfolio
from app.core.engine.StockTradeDataEngine import StockTradeDataEngine
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
        # buy 100 shares at 2030 (balance 197000)
        portfolio.buy(ts_code=ts_code, price=2030, hold_date=date(2022, 6, 29))
        # 2022-06-30 is ex-date of the fixture's cash dividend (2.0/share -> +200 cash),
        # and the fixture close is 1977.5 that day.
        portfolio.adjust_holding_shares(date(2022, 6, 30))
        self.assertEqual(197200 + 100 * 1977.5, portfolio.total)
        self.assertEqual(200, portfolio.benefit)
        self.assertEqual(197200, portfolio.balance)

    def test_merge_investments_with_same_code(self):
        ts_code = '600519.sh'
        portfolio = StubPortfolio.empty_portfolio(balance=400000)
        # buy 100 shares
        portfolio.buy(ts_code=ts_code, price=1800, hold_date=date(2023, 1, 20))

        # the fixture close on 2023-01-20 is 2050.5
        portfolio.update_current_price(date(2023, 1, 20))
        self.assertEqual(220000 + 100 * 2050.5, portfolio.total)
        self.assertEqual(220000, portfolio.balance)
        self.assertEqual('2023-01-20', portfolio.get_investment(ts_code).hold_date.strftime('%Y-%m-%d'))

        # buy another 100 shares
        shares, msg = portfolio.buy(ts_code=ts_code, price=1900, hold_date=date(2023, 1, 22))
        self.assertEqual(100, shares)
        self.assertEqual('Success', msg)

        self.assertEqual(220000 + 100 * 2050.5, portfolio.total)
        self.assertEqual(30000, portfolio.balance)
        self.assertEqual(1, len(portfolio.investments))
        self.assertEqual(10000, portfolio.get_investment(ts_code).benefit)
        self.assertEqual(1850, portfolio.get_investment(ts_code).buy_price)
        self.assertEqual(1900, portfolio.get_investment(ts_code).current_price)
        self.assertEqual('2023-01-20', portfolio.get_investment(ts_code).hold_date.strftime('%Y-%m-%d'))

    def test_sold_out_100_shares(self):
        portfolio = StubPortfolio.portfolio_with_100_shares_of_600519()

        portfolio.update_current_price(date(2023, 1, 20))
        self.assertEqual(2050.5, portfolio.investments[0].current_price)

        sell_shares, benefit = portfolio.sell(ts_code='600519.sh')
        self.assertEqual(100, sell_shares)
        self.assertEqual(25050, benefit)  # 100 * (2050.5 - 1800)

        self.assertEqual(25050, portfolio.benefit)
        # balance 20000 after the first buy + 100 * 2050.5
        self.assertEqual(20000 + 100 * 2050.5, portfolio.total)
        self.assertEqual(20000 + 100 * 2050.5, portfolio.balance)
        self.assertEqual(0, len(portfolio.investments))


