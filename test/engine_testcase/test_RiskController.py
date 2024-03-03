from datetime import date
from unittest import TestCase

from engine.RiskController import RiskController
from engine.StockTradeDataEngine import StockTradeDataEngine
from engine_testcase.StubPortfolio import StubPortfolio


class TestRiskController(TestCase):
    def test_evaluate_max_position_size(self):
        ts_code = '600519.sh'
        initial_investment = 400000
        parameters = {
            'risk_control.bearable_trading_loss': 0.01
        }

        data_engine = StockTradeDataEngine()
        portfolio = StubPortfolio.empty_portfolio(balance=initial_investment, data_engine=data_engine)
        risk_controller = RiskController(portfolio=portfolio, data_engine=data_engine, parameters=parameters)

        today = date(2023, 1, 19)
        trade_data = data_engine.get_trade_data_by_date(ts_code, today)
        max_position_size, atr = risk_controller.evaluate_buying_position_size(ts_code, trade_data)
        self.assertEqual(1, max_position_size)
        self.assertEqual(36.47, atr)
