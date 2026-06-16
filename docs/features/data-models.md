# Data models

Schema is applied by Alembic (`backend/alembic/versions/`). ORM models live in `backend/app/models/`.

## `public` schema (app)

| Table | Purpose |
|-------|---------|
| `users` | Local auth — login, password hash, `is_admin` |
| `jobs` | Background tasks — type, status, progress, payload, result, log |
| `portfolios` | Named portfolio configs (`config` JSON column) |
| `simulation_runs` | Backtest metadata — portfolio name, policy id, config snapshot |
| `simulation_daily` | Per-day equity curve for a run |
| `simulation_trades` | Individual trades for a run |

Migrations: `001_initial.py`, `003_portfolios.py`.

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
