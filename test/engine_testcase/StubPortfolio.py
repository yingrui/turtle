from datetime import date

from engine.Portfolio import Portfolio
from engine.StockTradeDataEngine import StockTradeDataEngine


class StubPortfolio:
    @staticmethod
    def empty_portfolio(balance=200000, data_engine=None):
        return Portfolio('mock', [], balance, 0, balance,
                         StockTradeDataEngine() if data_engine is None else data_engine)

    @staticmethod
    def portfolio_with_100_shares_of_600519():
        portfolio = StubPortfolio.empty_portfolio()
        portfolio.buy(ts_code='600519.sh', price=1800, hold_date=date(2023, 1, 20))
        return portfolio

    @staticmethod
    def mock_portfolio_with_200_shares_of_600519():
        portfolio = StubPortfolio.empty_portfolio(balance=400000)
        portfolio.buy(ts_code='600519.sh', price=1800, hold_date=date(2023, 1, 20))
        portfolio.buy(ts_code='600519.sh', price=1800, hold_date=date(2023, 1, 20))
        return portfolio
