from util.math_methods import round_down


class Investment:

    def __init__(self, ts_code, hold_shares, buy_price, current_price):
        self._ts_code = ts_code
        self._hold_shares = hold_shares
        self._payment = hold_shares * buy_price
        self._buy_price = buy_price
        self._current_price = current_price

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
    def payment(self):
        return self._payment

    @property
    def benefit(self):
        return round_down(self._current_price * self._hold_shares - self._payment)

    @property
    def current_price(self):
        return self._current_price

    def set_current_price(self, price):
        self._current_price = price

    def set_hold_shares(self, shares):
        self._hold_shares = shares

    def set_payment(self, payment):
        self._payment = payment

    def set_buy_price(self, price):
        self._buy_price = price
