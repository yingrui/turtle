# Data models

Schema is applied by Alembic (`backend/alembic/versions/`). ORM models live in `backend/app/models/`.

## `public` schema (app)

| Table | Purpose |
|-------|---------|
| `users` | Local auth — login, password hash, `is_admin` |
| `jobs` | Background tasks — type, status, progress, payload, result, log |
| `portfolios` | Named portfolios — `start_date`, `initial_investment`, `balance` |
| `portfolio_stocks` | One row per portfolio × stock (watchlist + holdings): shares, `avg_cost`, `total_cost`, `realized_pnl`, dates, risk fields |
| `portfolio_transactions` | The portfolio's **own** buy/sell ledger (manual, import, paper) — backtest fills are not here |
| `portfolio_risk_controls` | 1:1 risk parameters per portfolio |
| `portfolio_policies` | Ordered backtest policies with parameters (`params` JSON) |
| `portfolio_cash_flows` | Cash in/out per portfolio |
| `simulation_runs` | Backtest metadata — portfolio name/id, policy id, config snapshot, and the run's stored summary (return, CAGR, max drawdown, win/loss, trade count, window) |
| `simulation_daily` | Per-day equity curve for a run |
| `simulation_trades` | A run's fills (moved out of `portfolio_transactions` in migration `011`) |
| `simulation_holdings` | A run's positions at each close — "what did it hold on day X" |
| `factor_definitions` | Factor metadata — `code` (stable, unique), name, category, direction, logic, **`formula`** (null ⇒ definition only), params (JSONB), lookback, IC stats, source, and the coverage of the last compute (`value_count`, `stock_count`, `first_date`, `last_date`, `computed_at`) |
| `factor_values` | Factor panel — `(factor_id, ts_code, trade_date)` → `value`, optional `extra` for multi-output factors; PK is the natural key so a recompute upserts |

Migrations: `001_initial.py`, `003_portfolios.py`, `004_portfolio_normalization.py`, `005_simulation_summary.py`, `006_factor_library.py`, `007_factor_formula.py`, `008_factor_coverage.py`, `009_portfolio_lifecycle.py`, `010_simulation_holdings.py`, `011_simulation_trades.py`, `012_pool_modes.py`, `013_index_market_data.py`.

## `tushare` schema (market data)

Synced from Tushare via data collection jobs. Migration: `002_market_data.py`.

| Table | Purpose |
|-------|---------|
| `tushare.trade_calendar` | Exchange calendar |
| `tushare.index_basic` | Index metadata (~10.7k indexes); only a few carry daily bars |
| `tushare.index_daily` | Index OHLC per session — broad benchmarks: 000001.SH, 000300.SH, 000905.SH, 000852.SH, 399001.SZ, 399006.SZ (2024-01 → now) |
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
