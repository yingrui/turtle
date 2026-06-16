# API reference

Base URL: `http://localhost:8200` (host) or `/api` via the frontend proxy.

Interactive docs: **http://localhost:8200/docs** (OpenAPI).

All routes except `/health`, `/api/auth/mode`, `/api/auth/login`, and `/api/auth/register` require `Authorization: Bearer <jwt>`.

## Auth — `/api/auth`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/mode` | Auth mode (`local`) |
| POST | `/login` | Login → JWT |
| POST | `/register` | Register → JWT |
| GET | `/me` | Current user |

## Data — `/api/data`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/latest-date` | Latest synced trade date (`latest_date: null` if no market data yet) |

## Portfolios — `/api/portfolios`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | List portfolio names |
| POST | `/` | Create portfolio |
| GET | `/{name}` | Get config JSON |
| GET | `/{name}/yaml` | Get YAML representation |
| PUT | `/{name}` | Update config JSON |
| PUT | `/{name}/yaml` | Update from YAML body |
| DELETE | `/{name}` | Delete portfolio |

## Jobs — `/api/jobs`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | List jobs |
| GET | `/{job_id}` | Job detail |
| POST | `/` | Create job (data sync or simulation) |

## Screening — `/api/screening`

| Method | Path | Description |
|--------|------|-------------|
| POST | `/` | Run screen (returns job or results) |

## Simulations — `/api/simulations`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | List simulation runs |
| GET | `/compare` | Compare runs |
| GET | `/{run_id}/summary` | Run summary |
| GET | `/{run_id}/daily` | Daily equity series |
| GET | `/{run_id}/trades` | Trade list |
| GET | `/{run_id}/benefit` | Benefit chart data |
| GET | `/{run_id}/win-loss` | Win/loss stats |

## Stocks — `/api/stocks`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/search` | Symbol search (up to 20 matches by code, name, pinyin) |
| GET | `/universe/meta` | Latest trade date, listed count, exchange/market/industry facets |
| GET | `/universe/industry-summary` | Circ-mv-weighted change% by industry (`daily_basic.circ_mv` × `stock_trade_daily.pct_chg`) |
| GET | `/universe` | Paginated universe list with latest-day quote join |
| GET | `/` | List symbols in a portfolio (`?portfolio=name`) |
| GET | `/{ts_code}/snapshot` | Basic info + latest daily quote for one symbol |
| GET | `/{ts_code}/ohlcv` | QFQ-adjusted OHLCV series (`?limit=250`, max 2000) |
| GET | `/{ts_code}/indicators` | Technical indicators |
| POST | `/{ts_code}/forecast` | Forecast job |

### `GET /universe` query parameters

`q`, `exchange` (SH/SZ/BJ), `market`, `industry`, `list_status` (default `L`), `exclude_st` (default `true`), `page`, `page_size`, `sort`, `order`.

Sort fields: `ts_code`, `name`, `industry`, `list_date`, `open`, `high`, `low`, `close`, `pct_chg`, `vol`, `amount`.

Quote object on each universe item: `open`, `high`, `low`, `close`, `pre_close`, `pct_chg`, `vol`, `amount`, `trade_date`.

## Portfolios — watchlist

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/portfolios/{name}/watchlist` | Append `ts_code` to portfolio `follow_stocks` (deduped) |

## Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | `{"status":"ok"}` |
