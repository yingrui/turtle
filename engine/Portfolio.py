from engine.Investment import Investment
from util.math_methods import round_down


class Portfolio:

    def __init__(self, name, investments, balance, benefit, total):
        self._name = name
        self._balance = balance
        self._benefit = benefit
        self._investments = investments
        self._total = total

        self._min_investment_unit = 100

    @property
    def investments(self):
        return self._investments

    @property
    def balance(self):
        return self._balance

    @property
    def benefit(self):
        return self._benefit

    @property
    def total(self):
        return self._total

    def buy(self, ts_code, price):
        msg = 'Insufficient balance'
        buy_share = self._min_investment_unit
        if price * buy_share < self._balance:
            self._balance = self._balance - price * buy_share
            investment = Investment(ts_code, buy_share, price, price)
            exist_investment = self.get_investment(ts_code)
            if exist_investment is None:
                self._investments.append(investment)
            else:
                self._merge_investment(exist_investment, investment)
            msg = 'Success'
            return buy_share, msg
        return 0, msg

    def sell(self, ts_code):
        investment = self.get_investment(ts_code)
        if investment is not None:
            income = investment.hold_shares * investment.current_price
            self._balance = self._balance + income
            self._investments.remove(investment)
            self._benefit = round_down(self._benefit + investment.benefit)
            return investment.hold_shares, investment.benefit

    def get_investment(self, ts_code):
        return next(filter(lambda investment: investment.ts_code == ts_code, self._investments), None)

    def update_current_price(self, df_trade_data):
        if df_trade_data is None:
            return

        total = self._balance
        for investment in self._investments:
            close_price = df_trade_data[df_trade_data['ts_code'] == investment.ts_code.upper()]['close'].values[0]
            investment.set_current_price(close_price)
            total = total + investment.current_price * investment.hold_shares

        self._total = total

    @staticmethod
    def _merge_investment(exist_investment: Investment, investment: Investment):
        hold_shares = exist_investment.hold_shares + investment.hold_shares
        payment = exist_investment.payment + investment.payment
        buy_price = round_down(payment / hold_shares)

        exist_investment.set_hold_shares(hold_shares)
        exist_investment.set_payment(payment)
        exist_investment.set_buy_price(buy_price)
        exist_investment.set_current_price(investment.current_price)

    def __str__(self) -> str:
        brief = "Portfolio name: {0}, balance: {1}, benefit: {2}, total asset: {3}".format(self._name, self._balance,
                                                                                           self._benefit,
                                                                                           self._total)
        return brief
