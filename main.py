import argparse
from datetime import datetime
import multiprocess as mp

from configurer import load_yaml
from engine.Portfolio import Portfolio
from engine.StockTradeDataEngine import StockTradeDataEngine
from simulation.Simulator import Simulator
from util.date_methods import tomorrow


def run_simulation(config, start_date, end_date, policy_id):
    portfolio = Portfolio.create_portfolio(config, start_date, policy_id)
    simulator = Simulator(portfolio, config['follow_stocks'], StockTradeDataEngine(), config['risk_control'])

    simulator.set_policy(config['policies'][policy_id])
    simulator.run(start_date=start_date, end_date=end_date)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--configure', type=str, default='test.yaml', help='configure file')
    parser.add_argument('--start-date', type=str, default='2016-01-01', help='start date')
    parser.add_argument('--policy', type=int, default=None, help='specify policy index in configure file')
    opt = parser.parse_args()

    config = load_yaml(opt.configure)
    start_date = config.get('start_date', datetime.strptime(opt.start_date, "%Y-%m-%d").date())
    end_date = tomorrow()

    process_list = []
    policies = range(0, len(config['policies'])) if opt.policy is None else [opt.policy]
    for policy_id in policies:
        p = mp.Process(target=run_simulation, args=(config, start_date, end_date, policy_id))
        p.start()
        process_list.append(p)
