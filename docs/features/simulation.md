# Simulation

Backtests run a portfolio config + trading policy over historical data in `tushare.stock_trade_daily`.

## SPA

- **`/simulation`** — two columns: run configuration on the left, the eight most recent runs on the right (each links to its results) (portfolio, policy, date range).
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

## Model-driven runs (`mode="model"`)

A run can be driven by a scorecard instead of the configured trade policies. It ranks the **whole
market** each day, keeps a top-N book, and records the book at every close — so "what did it hold on
2026-05-14" is a lookup inside the run, not a fact about the live portfolio.

```http
POST /api/jobs
{"type": "simulation", "mode": "model", "portfolio": "top50-sim",
 "start_date": "2026-02-02", "end_date": "2026-10-09",
 "top_n": 50, "sell_rank_limit": 100, "cash_buffer": 0.05}
```

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `model_policy` | `expanding` | which model directory under `reports/models/` |
| `top_n` | 50 | the day's pool; names are bought equal-weight |
| `sell_rank_limit` | 2 × `top_n` | sell when the rank falls past this (leaving the pool does **not** sell) |
| `max_holding_days` | — | optional time stop |
| `cash_buffer` | 0.05 | share of equity kept in cash |
| `initial_cash` | 1,000,000 | starting capital of the run |

Rules are recorded in the run's `config_snapshot` and the run is stored with `mode='model'`. Each day
writes: `simulation_daily` (equity), `portfolio_transactions` (fills, tagged with the run), and
`simulation_holdings` (positions at the close, with the model's rank and score).

```http
GET /api/simulations/{run_id}/holdings?day=2026-05-14   # the book that day
GET /api/simulations/{run_id}/holding-dates             # which days have one
```

The run never touches `portfolio_stocks`: a backtest and the live portfolio are different books. A
portfolio can **point at** a run (`portfolios.active_run_id`), and then its stock pool comes from that
run — `fixed` (the configured watchlist) or `dynamic` (the model's top-N, recorded per day in
`simulation_pool`). See [Portfolio lifecycle](portfolio-lifecycle.md).
Models are read from `STOCK_MODELS_DIR` (default `reports/models`, baked into the image at build).

The results page overlays a benchmark: pick an index and the equity curve is drawn against it, both
rebased to 100 on the run's first day (163 days of the `d1139ccc` run: strategy 84.6 vs 沪深300 93.7,
i.e. **−9.1 points** — the comparison that says "this lost to the market", which a return percentage
alone cannot).

Measured over 2026-02-02 … 2026-10-09 with the current monthly models: 163 trading days, 6,224 fills,
final equity 845,759 (−15.4%), max drawdown −25.1%. Turnover is the dominant cost — see the note in
[Portfolio lifecycle](portfolio-lifecycle.md).

## API

List and query runs via `/api/simulations/*`. See [API reference](api-reference.md#simulations-apisimulations).

Engine: `app/core/simulation/Simulator.py`, orchestrated by `app/services/simulation_service.py`. Trade persistence happens in `job_service._persist_simulation_results`; `GET /api/simulations/{run_id}/trades` reads the same rows back from `portfolio_transactions`.
