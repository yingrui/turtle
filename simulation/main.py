from datetime import date

from engine.Portfolio import Portfolio
from engine.StockTradeDataEngine import StockTradeDataEngine
from engine.TradeEngine import TradeEngine
from simulation.Simulator import Simulator

if __name__ == "__main__":
    portfolio = Portfolio('test', [], 400000, 0, 400000)
    follow_stocks = ['600519.SH']

    data_engine = StockTradeDataEngine()
    trade_engine = TradeEngine(data_engine, follow_stocks=follow_stocks)
    simulator = Simulator(portfolio, trade_engine, data_engine)

    simulator.run(start_date=date(2016, 1, 1), end_date=date(2016, 1, 31))
