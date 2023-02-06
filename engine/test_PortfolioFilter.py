from datetime import date
from unittest import TestCase

from engine.PortfolioFilter import PortfolioFilter
from engine.StockTradeDataEngine import StockTradeDataEngine


class TestPortfolioFilter(TestCase):
    def test_filter(self):
        parameters = {
            'portfolio_filter.basic.ignore_st': True,
            'portfolio_filter.trend.moving_average.window_1': 50,
            'portfolio_filter.trend.moving_average.window_2': 150,
            'portfolio_filter.trend.moving_average.window_3': 250,
        }
        data_engine = StockTradeDataEngine()
        portfolio_filter = PortfolioFilter(data_engine, parameters)
        follow_stocks = portfolio_filter.filter(date(2020, 1, 4))
        print(follow_stocks)
        portfolio_filter.save()
