# Data models

Schema is applied by Alembic (`backend/alembic/versions/`). ORM models live in `backend/app/models/`.

## `public` schema (app)

| Table | Purpose |
|-------|---------|
| `users` | Local auth — login, password hash, `is_admin` |
| `jobs` | Background tasks — type, status, progress, payload, result, log |
| `portfolios` | Named portfolios — `start_date`, `initial_investment`, `balance` |
| `portfolio_stocks` | One row per portfolio × stock (watchlist + holdings): shares, `avg_cost`, `total_cost`, `realized_pnl`, dates, risk fields |
| `portfolio_transactions` | Buy/sell ledger; `simulation_run_id` marks backtest trades |
| `portfolio_risk_controls` | 1:1 risk parameters per portfolio |
| `portfolio_policies` | Ordered backtest policies with parameters (`params` JSON) |
| `portfolio_cash_flows` | Cash in/out per portfolio |
| `simulation_runs` | Backtest metadata — portfolio name/id, policy id, config snapshot, and the run's stored summary (return, CAGR, max drawdown, win/loss, trade count, window) |
| `simulation_daily` | Per-day equity curve for a run |

Migrations: `001_initial.py`, `003_portfolios.py`, `004_portfolio_normalization.py`, `005_simulation_summary.py`.

## `tushare` schema (market data)

Synced from Tushare via data collection jobs. Migration: `002_market_data.py`.

| Table | Purpose |
|-------|---------|
| `tushare.trade_calendar` | Exchange calendar |
| `tushare.stock_basic` | Symbol metadata |
| `tushare.stock_trade_daily` | Daily OHLCV (`ts_code`, `trade_date` PK) |
| `tushare.stock_adj_daily` | Adjustment factors |
| `tushare.daily_basic` | Daily valuation & share structure — PE/PB, `circ_mv`, `total_mv`, turnover, limit status |
| `tushare.dividends` | Dividend events |

Code references the schema via `app/core/tushare_schema.py` (`TUSHARE_SCHEMA`, `tushare_table()`).

### Grants (external Postgres)

If the app user is not the schema owner, grant access after migration:

```sql
GRANT USAGE ON SCHEMA tushare TO stock_user;
GRANT ALL ON ALL TABLES IN SCHEMA tushare TO stock_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA tushare GRANT ALL ON TABLES TO stock_user;
```

For PostgreSQL 15+ on `public`:

```sql
ALTER SCHEMA public OWNER TO stock_user;
-- or: GRANT ALL ON SCHEMA public TO stock_user;
```
