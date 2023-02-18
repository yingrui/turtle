import argparse
from datetime import datetime

from configurer import load_yaml
from engine.Portfolio import Portfolio
from engine.StockTradeDataEngine import StockTradeDataEngine
from simulation.Simulator import Simulator
from util.date_methods import tomorrow

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--configure', type=str, default='portfolio.yaml', help='start date')
    parser.add_argument('--default-start-date', type=str, default='2022-01-01', help='default start date')
    opt = parser.parse_args()

    config = load_yaml(opt.configure)
    start_date = config.get('start_date', datetime.strptime(opt.default_start_date, "%Y-%m-%d").date())
    end_date = tomorrow()

    for policy_id in range(0, 4):
        portfolio = Portfolio.create_portfolio(config, start_date, policy_id)
        simulator = Simulator(portfolio, config['follow_stocks'], StockTradeDataEngine(), config['risk_control'])

        simulator.set_policy(config['policies'][policy_id])
        simulator.run(start_date=start_date, end_date=end_date)
