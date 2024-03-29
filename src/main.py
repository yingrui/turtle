import argparse
from datetime import datetime, date
import multiprocess as mp

from configurer import load_yaml
from engine.Portfolio import Portfolio
from engine.StockTradeDataEngine import StockTradeDataEngine
from simulation.Simulator import Simulator
from util.date_methods import tomorrow


def run_simulation(config, start_date, end_date, policy_id):
    portfolio = Portfolio.create_portfolio(config, start_date, policy_id)

    policy_parameter = config['policies'][policy_id]
    risk_control_parameter = {**policy_parameter, **config['risk_control']}
    simulator = Simulator(portfolio, config['follow_stocks'], StockTradeDataEngine(), risk_control_parameter,
                          increase_investments=config.get('increase_investments', []))
    simulator.set_policy(policy_parameter)
    simulator.run(start_date=start_date, end_date=end_date)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--configure', type=str, default='portfolio.yaml', help='configure file')
    parser.add_argument('--start-date', type=str, default='2016-01-01', help='start date')
    parser.add_argument('--end-date', type=str, default=date.today().strftime('%Y-%m-%d'), help='end date')
    parser.add_argument('--policy', type=int, default=None, help='specify policy index in configure file')
    opt = parser.parse_args()

    config = load_yaml(opt.configure)
    start_date = config.get('start_date', datetime.strptime(opt.start_date, "%Y-%m-%d").date())
    end_date = config.get('end_date', datetime.strptime(opt.end_date, "%Y-%m-%d").date())

    if opt.policy is None:
        process_list = []
        policies = range(0, len(config['policies']))
        for policy_id in policies:
            p = mp.Process(target=run_simulation, args=(config, start_date, end_date, policy_id))
            p.start()
            process_list.append(p)
    else:
        run_simulation(config, start_date, end_date, opt.policy)
