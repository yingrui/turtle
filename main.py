from datetime import date

from configurer import load_yaml
from engine.Portfolio import Portfolio
from engine.StockTradeDataEngine import StockTradeDataEngine
from simulation.Simulator import Simulator
from util.date_methods import tomorrow

if __name__ == "__main__":
    # config = load_yaml('portfolio.yaml')
    config = load_yaml('test.yaml')

    default_start_date = date(2016, 1, 1)
    start_date = config.get('start_date', default_start_date)
    end_date = tomorrow()

    portfolio = Portfolio.create_portfolio(config, start_date)
    simulator = Simulator(portfolio, config['follow_stocks'], StockTradeDataEngine(), config['risk_control'])

    simulator.set_policy(config['policies'][1])
    simulator.run(start_date=start_date, end_date=end_date)
