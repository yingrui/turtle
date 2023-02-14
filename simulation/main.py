from datetime import date

from configurer import follow_stocks
from engine.Portfolio import Portfolio
from engine.StockTradeDataEngine import StockTradeDataEngine
from engine.TradeSignalMonitor import TradeSignalMonitor
from simulation.Simulator import Simulator
from util.date_methods import tomorrow

if __name__ == "__main__":
    initial_investment = 400000
    parameters = {
        'trade_policy.moving_average.window_1': 20,
        'trade_policy.moving_average.window_2': 70,
        'risk_control.bearable_trading_loss': 0.01,
        'risk_control.position_control': 1.0,
        'risk_control.position_control.reserve_profit': 0.1,
        'risk_control.max_position_size': 50,
        'risk_control.stop_loss_point.should_check': True,
        'risk_control.stop_loss_point.n_times_atr': 2,
        'risk_control.max_holding_period.should_check': True,
        'risk_control.max_holding_period.days': 80,
    }

    data_engine = StockTradeDataEngine()
    portfolio = Portfolio('test', [], initial_investment, 0, initial_investment, data_engine)
    trade_engine = TradeSignalMonitor(data_engine, follow_stocks=follow_stocks(), parameters=parameters)

    simulator = Simulator(portfolio, trade_engine, data_engine, parameters)

    simulator.run(start_date=date(2020, 1, 1), end_date=tomorrow())
