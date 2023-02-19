import argparse
from datetime import datetime

from configurer import load_yaml
from engine.Portfolio import Portfolio
from engine.StockTradeDataEngine import StockTradeDataEngine
from simulation.Simulator import Simulator
from util.date_methods import tomorrow

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--configure', type=str, default='test.yaml', help='configure file')
    parser.add_argument('--start-date', type=str, default='2016-01-01', help='start date')
    parser.add_argument('--policy', type=int, default=None, help='specify policy index in configure file')
    opt = parser.parse_args()

    config = load_yaml(opt.configure)
    start_date = config.get('start_date', datetime.strptime(opt.start_date, "%Y-%m-%d").date())
    end_date = tomorrow()

    simulator_list= []
    policies = range(0, len(config['policies'])) if opt.policy is None else [opt.policy]
    for policy_id in policies:
        portfolio = Portfolio.create_portfolio(config, start_date, policy_id)
        simulator = Simulator(portfolio, config['follow_stocks'], StockTradeDataEngine(), config['risk_control'])

        simulator.set_policy(config['policies'][policy_id])
        simulator.run(start_date=start_date, end_date=end_date)
        simulator_list.append(simulator)

    for simulator in simulator_list:
        simulator.print_summary()