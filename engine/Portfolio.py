import pandas as pd

from engine.Investment import Investment
from engine.StockTradeDataEngine import StockTradeDataEngine
from util.math_methods import round_down


class Portfolio:

    def __init__(self, name, investments, balance, benefit, total, data_engine):
        self._name = name
        self._balance = balance
        self._benefit = benefit
        self._investments = investments
        self._total = total
        self._initial_investment = total
        self._data_engine = data_engine
        self._investment_total = 0

        self._min_investment_unit = 100

    @property
    def name(self):
        return self._name

    @property
    def investments(self):
        return self._investments

    @property
    def initial_investment(self):
        return self._initial_investment

    @property
    def return_rate(self):
        return round_down(self._total / self._initial_investment * 100)

    @property
    def investment_total(self):
        return self._investment_total

    @property
    def balance(self):
        return self._balance

    @property
    def benefit(self):
        return self._benefit

    @property
    def total(self):
        return self._total

    def has_stock(self, ts_code):
        for investment in self._investments:
            if investment.ts_code == ts_code:
                return True

        return False

    def buy(self, ts_code, price, hold_date, position_size=1, position_control=1, stop_loss_point=0):
        msg = 'Insufficient balance'
        buy_share = self._find_affordable_shares(price, position_size, position_control)
        if buy_share > 0 and price * buy_share < self._balance:
            self._balance = round_down(self._balance - price * buy_share)
            investment = Investment(ts_code, buy_share, price, price, hold_date, stop_loss_point)
            exist_investment = self.get_investment(ts_code)
            if exist_investment is None:
                self._investments.append(investment)
            else:
                self._merge_investment(exist_investment, investment)
            msg = 'Success'
            return buy_share, msg
        return 0, msg

    def _find_affordable_shares(self, price, max_lots_of_stock, position_control):
        for n in range(max_lots_of_stock, 0, -1):
            shares = n * self._min_investment_unit
            if price * shares < self._balance:
                position = 1 - (self._balance - price * shares) / self.total
                if position <= position_control:
                    return shares
        return 0

    def sell(self, ts_code):
        investment = self.get_investment(ts_code)
        if investment is not None:
            income = investment.hold_shares * investment.current_price
            self._balance = round_down(self._balance + income)
            self._investments.remove(investment)
            self._benefit = round_down(self._benefit + investment.benefit)
            return investment.hold_shares, investment.benefit

    def get_investment(self, ts_code):
        return next(filter(lambda investment: investment.ts_code == ts_code, self._investments), None)

    def adjust_holding_shares(self, current_date):
        for investment in self._investments:
            dividents = self._data_engine.get_dividents_data_on_date(investment.ts_code, current_date)
            if dividents.shape[0] > 0:
                investment.process_dividents(dividents.stk_div.values[0], dividents.stk_bo_rate.values[0],
                                             dividents.stk_co_rate.values[0], dividents.cash_div.values[0],
                                             dividents.cash_div_tax.values[0], dividents.record_date.values[0])
                if investment.cash_return > 0:
                    cash_return = investment.withdraw_cash_return()
                    self._balance = self._balance + cash_return
                    self._benefit = self._benefit + cash_return

        self.update_current_price(current_date)

    def update_current_price(self, current_date):
        if current_date is None:
            return

        total = self._balance
        investment_total = 0
        for investment in self._investments:
            close_price, high, low = self._data_engine.get_stock_price_on_date(investment.ts_code, current_date)
            investment.set_current_price(close_price)
            investment_total = investment_total + investment.total

        self._investment_total = round_down(investment_total)
        self._total = round_down(total + investment_total)

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
        brief = "Portfolio: {0}, initial:{1}, balance: {2}, benefit: {3}, investment: {4}, total asset: {5}, ".format(
            self._name, self._initial_investment, self._balance, self._benefit, self._investment_total, self._total)

        return_rate = 'return rate: {0} %'.format(self.return_rate)
        investments = ' | '.join(map(lambda i: str(i), self._investments))
        return brief + return_rate + ' | ' + investments

    @staticmethod
    def create_portfolio(config, start_date):
        name = config['name']
        initial_investment = config['initial_investment']
        balance = config.get('balance', 0)
        exists_investments = config.get('investments', [])
        investments = []
        investment_total = 0
        data_engine = StockTradeDataEngine()
        for i in exists_investments:
            current_price, high, low = data_engine.get_stock_price_on_date(i['ts_code'], start_date)
            investment = Investment(i['ts_code'], i['hold_shares'], i['buy_price'],
                                    current_price, pd.Timestamp(start_date))
            investments.append(investment)
            investment_total = investment_total + investment.total

        benefit = initial_investment - balance - investment_total
        balance = balance + benefit
        return Portfolio(name, investments, balance, 0, initial_investment, data_engine)
