import pandas as pd
from datetime import date

from engine.PortfolioFilter import PortfolioFilter
from engine.StockTradeDataEngine import StockTradeDataEngine

if __name__ == "__main__":
    parameters = {
        'portfolio_filter.basic.ignore_st': True,
        'portfolio_filter.trend.moving_average.window_1': 20,
        'portfolio_filter.trend.moving_average.window_2': 70,
        'portfolio_filter.trend.moving_average.window_3': 150,
    }
    data_engine = StockTradeDataEngine()
    portfolio_filter = PortfolioFilter(data_engine, parameters)
    follow_stocks = portfolio_filter.filter(date(2023, 2, 1))
    portfolio_filter.save()

    df = pd.read_csv('portfolio.csv')
    df = df.sort_values(by=['gradient'], ascending=False)
    print(df.head())