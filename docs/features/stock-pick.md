# Stock picking (基本面选股)

Synchronous fundamental stock picking on `stock_basic` + `daily_basic` at the latest trade date (or `as_of_date`).

## API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/stock-pick` | Run pick with JSON filters |
| GET | `/api/stock-pick/presets` | Built-in preset templates |

Requires `daily_basic` data from external ETL. Check [Data status](data-sync.md) / `GET /api/data/status` first.

## Filters (all optional)

| Field | Description |
|-------|-------------|
| `as_of_date` | Cross-section date (default: latest `stock_trade_daily`) |
| `q` | Code / name / pinyin search |
| `industry` | Exact industry |
| `list_status` | Default `L` (listed) |
| `exclude_st` | Default `true` |
| `exclude_limit` | Exclude limit-up/down / suspended (`limit_status`) |
| `pe_ttm_min` / `pe_ttm_max` | PE (TTM) range |
| `pb_min` / `pb_max` | PB range |
| `ps_ttm_min` / `ps_ttm_max` | PS (TTM) range |
| `circ_mv_min` / `circ_mv_max` | Circulating market cap (万元) |
| `total_mv_min` / `total_mv_max` | Total market cap (万元) |
| `turnover_rate_min` / `turnover_rate_max` | Turnover rate % |
| `sort` | `circ_mv`, `pe_ttm`, `pb`, `pct_chg`, etc. |
| `order` | `asc` / `desc` |
| `limit` | Max rows (default 200, max 500) |

## UI

Route **`/screening`** — **基本面** tab calls `POST /api/stock-pick`; results support watchlist bulk add and simulation with `ts_codes` override.

## Presets

`GET /api/stock-pick/presets` returns templates such as low PE, small cap, high turnover for one-click form fill.
