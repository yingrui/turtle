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

The page is split into tabs: **Overview** (holdings/watching counts, market value, cost basis,
unrealized and realized P&L, position weights, cost-vs-price bullets and a *Backtest this
portfolio* hand-off to `/simulation?portfolio=<name>`), **Holdings**, **Trades**, **Risk &
policies** and **Advanced (YAML)**.

The cost-vs-price bullets plot, per holding, the cost basis (grey), the latest price (red/green
by direction) and the stop loss (dark) on one scale — so a position sitting on its stop is
visually obvious. **Trades** links a backtest trade's run id to `/simulation/results?run_id=…`.

**Holdings** carries a risk column built from the stored risk settings: stop-loss distance ("stop
hit" when the latest close is at or below `stop_loss_point`, "near stop" within 3%), holding-period
budget (`max_holding_days` vs `holding_days`) and position weight vs `max_position_ratio`.

**Risk & policies** edits the ten risk parameters through a form (they are also visible in the YAML
tab as flattened `snake.case` keys) and lists the backtest policies read-only.

The holdings tab is split by status with a **segmented control** (`watching` / `holding` /
`closed`, deep-linkable via `?tab=holdings&status=…`); the table carries the actionable columns and
a **row click opens a detail drawer** with the low-frequency fields (累计成本、已实现、首次买入、
最后交易) plus editable stop loss / target amount / max holding days. `/watchlist` redirects to
`/portfolio?tab=holdings&status=watching`.

The holdings table has per-row actions: **Buy** / **Sell** open a drawer that records a trade
(方向、日期、股数、价格、费用、备注) and then refreshes the row; **Remove** drops a stock that is not
held. Stock codes link to the stock detail page. The drawer is bookkeeping only — it never sends
an order to a broker; it writes a ledger row and the position aggregates in one transaction.

Empty states point at the screening page, and holding rows show latest price, market value and
unrealized P&L from the latest market quote.

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

Reads of `GET /api/portfolios/{name}/stocks` additionally join the latest market quote for held
positions and return `current_price`, `price_date`, `market_value`, `unrealized_pnl` and
`unrealized_pct`. Those are computed on read (never stored), so they stay correct as prices move;
`holding_days` is likewise derived from `first_buy_date`.

Holding period: `portfolio_transactions.trade_date` is the buy/sell date, and
`portfolio_stocks.first_buy_date` / `last_trade_date` carry the start and end of the **current**
holding streak — closing a position clears `first_buy_date`, so re-buying later restarts
`holding_days`; realized P&L still accumulates across streaks. The holdings table shows the
held-days count next to the first-buy date.

Cost basis is weighted average: buys re-weight `avg_cost`, sells realize
`(price − avg_cost) × shares` into `realized_pnl` and leave `avg_cost` unchanged. Rows with
`simulation_run_id` set (backtest trades) never touch the live aggregates.

## Equity curve

`GET /api/portfolios/{name}/equity` rebuilds the daily market value from
`portfolio_transactions` + daily closes instead of reading a snapshot table: positions are
replayed from the ledger, valued with that day's close, and cost basis / realized P&L come along.
Trade-off — recomputation on every read (cheap for a personal portfolio) buys correctness after a
backfilled trade or a corrected price, which a nightly snapshot would miss.

## API

See [API reference — Portfolios](api-reference.md#portfolios-apiportfolios).

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
