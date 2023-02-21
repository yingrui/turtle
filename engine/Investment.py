import pandas as pd

from util.math_methods import round_down


class Investment:

    def __init__(self, ts_code, hold_shares, buy_price, current_price, hold_date, stop_loss_point=0):
        self._ts_code = ts_code
        self._hold_shares = hold_shares
        self._payment = hold_shares * buy_price
        self._buy_price = buy_price
        self._current_price = current_price
        self._hold_date = hold_date
        self._stop_loss_point = stop_loss_point
        self._cash_return = 0
        self._total_cash_return = 0

    @property
    def ts_code(self):
        return self._ts_code

    @property
    def buy_price(self):
        return self._buy_price

    @property
    def hold_shares(self):
        return self._hold_shares

    @property
    def hold_date(self):
        return self._hold_date

    @property
    def payment(self):
        return self._payment

    @property
    def cash_return(self):
        return self._cash_return

    @property
    def total_cash_return(self):
        return self._total_cash_return

    @property
    def benefit(self):
        return round_down(self._current_price * self._hold_shares + self._total_cash_return - self._payment)

    @property
    def current_price(self):
        return self._current_price

    @property
    def stop_loss_point(self):
        return self._stop_loss_point

    @property
    def total(self):
        return round_down(self._current_price * self._hold_shares + self._cash_return)

    def set_current_price(self, price):
        self._current_price = price

    def withdraw_cash_return(self):
        ret = self._cash_return
        self._cash_return = 0
        return ret

    def set_hold_shares(self, shares):
        self._hold_shares = shares

    def set_payment(self, payment):
        self._payment = payment

    def set_buy_price(self, price):
        self._buy_price = price

    def process_dividents(self, stk_div, stk_bo_rate, stk_co_rate, cash_div, cash_div_tax, record_date):
        if pd.Timestamp(self.hold_date) > pd.Timestamp(record_date):
            return

        if cash_div > 0.0:
            self._cash_return = self._cash_return + cash_div * self._hold_shares
            self._total_cash_return = round_down(self._total_cash_return + cash_div * self._hold_shares)

        if stk_div > 0.0:
            self._hold_shares = self._hold_shares + stk_div * self._hold_shares

    def __str__(self) -> str:
        return "{0}: {1} {2}".format(self._ts_code, int(self._hold_shares / 100), self.total)
