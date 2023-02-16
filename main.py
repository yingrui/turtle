from datetime import date

from configurer import load_yaml
from engine.Portfolio import Portfolio
from engine.StockTradeDataEngine import StockTradeDataEngine
from engine.TradeSignalMonitor import TradeSignalMonitor
from simulation.Simulator import Simulator
from util.date_methods import tomorrow

if __name__ == "__main__":
    config = load_yaml('portfolio.yaml')
    initial_investment = 400000

    data_engine = StockTradeDataEngine()
    portfolio = Portfolio(config['name'], [], initial_investment, 0, initial_investment, data_engine)
    trade_engine = TradeSignalMonitor(data_engine, follow_stocks=config['follow_stocks'], parameters=config['policies'][0])

    simulator = Simulator(portfolio, trade_engine, data_engine, config['policies'][0])

    simulator.run(start_date=date(2023, 1, 1), end_date=tomorrow())
