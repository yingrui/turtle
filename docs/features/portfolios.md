# Portfolios

Portfolio data lives in PostgreSQL. Stocks, trades, risk parameters, policies and cash flows are
stored relationally — there is no config JSON column on `portfolios`.

The UI keeps a YAML editor for convenience; the API accepts both a structured payload and the
legacy config dict, and composes that dict back on read.

## SPA

Route: **`/portfolio`**

Create, select, edit, and delete named portfolios. The portfolio page shows the stocks of the
portfolio (`portfolio_stocks`), the buy/sell ledger (`portfolio_transactions`) and the
risk-control / policy parameters.

## Storage

| Table | Holds |
|-------|-------|
| `portfolios` | Name, `start_date`, `initial_investment`, `balance` |
| `portfolio_stocks` | One row per portfolio × stock: watchlist + holdings, cost basis, realized P&L, risk fields |
| `portfolio_transactions` | Buy/sell ledger; `simulation_run_id` marks backtest trades |
| `portfolio_risk_controls` | 1:1 risk parameters (stop loss, position limits, holding period) |
| `portfolio_policies` | Ordered backtest policies with their parameters |
| `portfolio_cash_flows` | Cash in/out (replaces the legacy `increase_investments` list) |

`portfolio_stocks.hold_shares` / `avg_cost` / `total_cost` / `realized_pnl` / `last_trade_date`
are aggregates over the ledger. `PortfolioService.record_transaction` maintains them in the same
transaction as the ledger row; `POST /api/portfolios/{name}/stocks/{ts_code}/rebuild` recomputes
them from the ledger.

Cost basis is weighted average: buys re-weight `avg_cost`, sells realize
`(price − avg_cost) × shares` into `realized_pnl` and leave `avg_cost` unchanged. Rows with
`simulation_run_id` set (backtest trades) never touch the live aggregates.

## API

See [API reference — Portfolios](api-reference.md#portfolios-apportfolios).

- Stocks: `GET|POST /api/portfolios/{name}/stocks`, `PATCH|DELETE .../stocks/{ts_code}`
- Ledger: `GET|POST /api/portfolios/{name}/transactions`
- Parameters: `GET|PUT .../risk-control`, `GET|PUT .../policies`, `GET|POST .../cash-flows`
- Config view: `GET /api/portfolios/{name}` composes the engine-facing dict
  (`follow_stocks`, `investments`, `risk_control`, `policies`); `PUT` decomposes it back into
  tables
- YAML: `GET|PUT /api/portfolios/{name}/yaml`

## Engine usage

Simulation and screening services load the composed config via
`PortfolioService(db).get_portfolio(name)` before running the engine in `app/core/`.
