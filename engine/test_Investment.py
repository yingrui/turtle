from datetime import date
from unittest import TestCase

from engine.Investment import Investment
from util.math_methods import round_down


class TestInvestment(TestCase):

    def test_process_cash_return(self):
        hold_shares = 100
        cost_price = 2030
        current_price = 2045
        investment = Investment('600519.SH', hold_shares, cost_price, current_price, date(2022, 6, 29))
        cash_return_per_share = 21.675
        investment.process_dividents(0.0, None, None, cash_return_per_share, cash_return_per_share, date(2022, 6, 29))

        self.assertEqual(hold_shares, investment.hold_shares)
        self.assertEqual(cash_return_per_share * hold_shares, investment.cash_return)

        expect_total = round_down((current_price + cash_return_per_share) * hold_shares)
        expect_benefit = round_down((current_price - cost_price) * hold_shares + cash_return_per_share * hold_shares)
        self.assertEqual(expect_total, investment.total)
        self.assertEqual(expect_benefit, investment.benefit)

    def test_process_cash_return_should_check_record_date(self):
        hold_shares = 100
        cost_price = 2030
        current_price = 2045
        investment = Investment('600519.SH', hold_shares, cost_price, current_price, date(2022, 6, 30))
        cash_return_per_share = 21.675
        investment.process_dividents(0.0, None, None, cash_return_per_share, cash_return_per_share, date(2022, 6, 29))

        self.assertEqual(hold_shares, investment.hold_shares)
        self.assertEqual(0, investment.cash_return)

    def test_process_share_dividents(self):
        hold_shares = 100
        share_div = 0.1
        cost_price = 251.59
        current_price = 228.29
        investment = Investment('600519.SH', hold_shares, cost_price, current_price, date(2015, 7, 16))
        cash_return_per_share = 4.1503
        investment.process_dividents(share_div, share_div, None, cash_return_per_share, 4.3740, date(2015, 7, 16))

        self.assertEqual(hold_shares + hold_shares * share_div, investment.hold_shares)
        self.assertEqual(cash_return_per_share * hold_shares, investment.cash_return)
