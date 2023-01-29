from datetime import date

from engine.Portfolio import Portfolio
from engine.TradeEngine import TradeEngine
from simulation.Simulator import Simulator

if __name__ == "__main__":
    portfolio = Portfolio('mock', [], 400000, 0, 400000)
    trade_engine = TradeEngine(follow_stocks=['600519.SH'])
    simulator = Simulator(portfolio, trade_engine)
    simulator.run(start_date=date(2015, 4, 1), end_date=date(2015, 12, 31))
