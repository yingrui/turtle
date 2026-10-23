# Simulation

Backtests run a portfolio config + trading policy over historical data in `tushare.stock_trade_daily`.

## SPA

- **`/simulation`** — configure and start a simulation job (portfolio, policy, date range).
  Accepts `?portfolio=<name>` to preselect a portfolio (used by the portfolio page's
  *Backtest this portfolio* button).
- **`/simulation/results`** — compare runs, equity curves, trade tables; `?run_id=<id>` deep-links
  a single run (used by the portfolio page's trade log).

## Persistence

When a simulation completes:

- `simulation_runs` — run metadata (now also linked to `portfolio_id`) and config snapshot, plus
  the run's **summary**: `window_start`/`window_end`, `initial_total`, `final_total`,
  `return_rate_pct` (100-based), `cagr`, `years`, `max_drawdown_pct`, `win_count`, `loss_count`,
  `holding_count`, `trade_count`. It is computed once by `summarize_run` when the run finishes, so
  a reader does not have to replay the daily log; older rows are filled by
  `scripts/backfill_simulation_summaries.py` (`--force` recomputes)
- `simulation_daily` — daily returns, balance, benefit
- `portfolio_transactions` — buy/sell rows tagged with `simulation_run_id` (daily holding snapshots are no longer stored; positions are replayable from the ledger)

Logs may also be written under `STOCK_LOGS_DIR`.

## API

List and query runs via `/api/simulations/*`. See [API reference](api-reference.md#simulations-apisimulations).

Engine: `app/core/simulation/Simulator.py`, orchestrated by `app/services/simulation_service.py`. Trade persistence happens in `job_service._persist_simulation_results`; `GET /api/simulations/{run_id}/trades` reads the same rows back from `portfolio_transactions`.
