from datetime import date
from unittest import TestCase

import pandas as pd

from engine.InvestmentLogger import InvestmentLogger
from engine.Portfolio import Portfolio
from engine.StockTradeDataEngine import StockTradeDataEngine


class TestInvestmentLogger(TestCase):

    def test_log(self):
        logger, portfolio = self._simulate(start_date=date(2020, 1, 1), end_date=date(2020, 1, 10))
        df_daily = logger.get_daily_log()
        self.assertEqual(7, df_daily.shape[0])

    def test_log_when_cross_years(self):
        logger, portfolio = self._simulate(start_date=date(2020, 1, 1), end_date=date(2022, 1, 4))
        df_daily = logger.get_daily_log()
        self.assertEqual(487, df_daily.shape[0])
        initial_total, total, years, compound_annual_growth_rate = logger.get_summary()
        self.assertEqual(2, years)
        self.assertEqual(0.2, compound_annual_growth_rate)

    @staticmethod
    def _simulate(start_date, end_date):
        name = 'mock'
        data_engine = StockTradeDataEngine()
        portfolio = Portfolio(name, [], 200000, 0, 200000, data_engine)
        portfolio.buy(ts_code='600519.sh', price=1130, hold_date=start_date)

        logger = InvestmentLogger(name, './logs')

        for current_date in pd.date_range(start=start_date, end=end_date):
            if data_engine.is_trade_day(current_date):
                portfolio.update_current_price(current_date)
                logger.log_portfolio(portfolio, current_date)

        return logger, portfolio
