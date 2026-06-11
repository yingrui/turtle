"""Simulation runner extracted from CLI entry point."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import multiprocess as mp

from app.core.configurer import load_yaml
from app.core.engine.InvestmentLogger import InvestmentLogger
from app.core.engine.Portfolio import Portfolio
from app.core.engine.StockTradeDataEngine import StockTradeDataEngine
from app.core.simulation.Simulator import Simulator


def run_simulation(
    config: dict[str, Any],
    start_date: date,
    end_date: date,
    policy_id: int,
    *,
    logs_folder: str = "logs",
    logger_sink: InvestmentLogger | None = None,
) -> InvestmentLogger:
    portfolio = Portfolio.create_portfolio(config, start_date, policy_id)
    policy_parameter = config["policies"][policy_id]
    risk_control_parameter = {**policy_parameter, **config["risk_control"]}
    simulator = Simulator(
        portfolio,
        config["follow_stocks"],
        StockTradeDataEngine(),
        risk_control_parameter,
        increase_investments=config.get("increase_investments", []),
        logs_folder=logs_folder,
        logger_sink=logger_sink,
    )
    simulator.set_policy(policy_parameter)
    simulator.run(start_date=start_date, end_date=end_date)
    return simulator.logger


def run_all_policies(
    config_path: str,
    start_date: date | None = None,
    end_date: date | None = None,
    policy_id: int | None = None,
    *,
    logs_folder: str = "logs",
) -> list[InvestmentLogger]:
    config = load_yaml(config_path)
    start = start_date or config.get("start_date")
    if isinstance(start, str):
        start = datetime.strptime(start, "%Y-%m-%d").date()
    end = end_date or config.get("end_date", date.today())
    if isinstance(end, str):
        end = datetime.strptime(end, "%Y-%m-%d").date()

    if policy_id is not None:
        return [run_simulation(config, start, end, policy_id, logs_folder=logs_folder)]

    process_list: list[mp.Process] = []
    for pid in range(len(config["policies"])):
        p = mp.Process(
            target=run_simulation,
            args=(config, start, end, pid),
            kwargs={"logs_folder": logs_folder},
        )
        p.start()
        process_list.append(p)
    for p in process_list:
        p.join()

    loggers: list[InvestmentLogger] = []
    portfolio_name = config.get("name", "portfolio")
    for pid in range(len(config["policies"])):
        name = f"{portfolio_name}-{pid}"
        logger = InvestmentLogger(name, folder=logs_folder, open_console=False)
        logger.load_from_disk()
        loggers.append(logger)
    return loggers
