import datetime

import pandas as pd

from engine.TrendAnalyzer import TrendAnalyzer


class PortfolioFilter:

    def __init__(self, data_engine, parameters={}):
        self._data_engine = data_engine
        self._df_portfolio = pd.DataFrame({
            'date': [], 'ts_code': [], 'gradient': [], 'stationary': []
        })
        self._ignore_st = parameters.get('portfolio_filter.basic.ignore_st', False)
        self._parameters = parameters

    def filter(self, current_date):
        df_stocks = self._data_engine.list_stocks_on_date(current_date)
        df_stocks = self.filter_st_stocks(df_stocks)

        for index, stock in df_stocks.iterrows():
            start_date = current_date - datetime.timedelta(days=2 * 365)
            end_date = current_date - datetime.timedelta(days=1)
            time_series = self._data_engine.get_trade_data_by_code(stock.ts_code, start_date, end_date)
            trend_analyzer = TrendAnalyzer(ts_code=stock.ts_code, trade_data=time_series, parameters=self._parameters)
            trend = trend_analyzer.analysis_trend()
            print(stock.ts_code, stock['name'], stock.industry, trend)
            if trend.status == 'up':
                df = pd.DataFrame({'date': [current_date], 'ts_code': [stock.ts_code],
                                   'gradient': [trend.gradient], 'stationary': [trend.stationary]})
                self._df_portfolio = pd.concat([self._df_portfolio, df], ignore_index=True)

        return self._df_portfolio

    def filter_st_stocks(self, df_stocks):
        if self._ignore_st:
            return df_stocks[~df_stocks["name"].str.contains("ST")]
        return df_stocks

    def save(self, file='portfolio.csv'):
        df = self._df_portfolio[self._df_portfolio.gradient > 0.1]
        df = df[df.stationary < 0.05]
        df.sort_values(by=['stationary'], ascending=True).to_csv(file, index=False)
