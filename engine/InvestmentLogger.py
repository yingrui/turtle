import pandas as pd
from datetime import date

from util.math_methods import round_down


class InvestmentLogger:

    def __init__(self, name):
        self._name = name
        self._df_daily = pd.DataFrame({
            'date': [], 'return_rate': [], 'balance': [], 'benefit': [], 'investment_total': [], 'total': []
        })

    def log(self, portfolio, current_date):
        self._log_daily_information(current_date, portfolio)

    def _log_daily_information(self, current_date, portfolio):
        df = pd.DataFrame({
            'date': [current_date], 'return_rate': [portfolio.return_rate], 'balance': [portfolio.balance],
            'benefit': [portfolio.benefit], 'investment_total': [portfolio.investment_total],
            'total': [portfolio.total]
        })
        self._df_daily = pd.concat([self._df_daily, df], ignore_index=True)

    def get_summary(self):
        start_date = date.fromtimestamp(self._df_daily.date.values[0].astype(int) / 1e9)
        end_date = date.fromtimestamp(self._df_daily.date.values[-1].astype(int) / 1e9)
        years = end_date.year - start_date.year if end_date.year > start_date.year else 1
        initial_total = self._df_daily.total.values[0]
        total = self._df_daily.total.values[-1]
        compound_annual_growth_rate = round_down((total / initial_total) ** (1 / years) - 1)
        return initial_total, total, years, compound_annual_growth_rate

    def get_daily_log(self):
        return self._df_daily

    def save(self):
        self._df_daily.to_csv('{0}.log'.format(self._name), index=False)
