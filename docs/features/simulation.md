# Simulation

Backtests run a portfolio config + trading policy over historical data in `tushare.stock_trade_daily`.

## SPA

- **`/simulation`** — configure and start a simulation job (portfolio, policy, date range)
- **`/simulation/results`** — compare runs, equity curves, trade tables

## Persistence

When a simulation completes:

- `simulation_runs` — run metadata and config snapshot
- `simulation_daily` — daily returns, balance, benefit
- `simulation_trades` — individual trades with reasons

Logs may also be written under `STOCK_LOGS_DIR`.

## API

List and query runs via `/api/simulations/*`. See [API reference](api-reference.md#simulations-apisimulations).

Engine: `app/core/simulation/Simulator.py`, orchestrated by `app/services/simulation_service.py`.
