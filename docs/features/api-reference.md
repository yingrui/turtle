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
| GET | `/search` | Symbol search |
| GET | `/` | List symbols |
| GET | `/{ts_code}/ohlcv` | OHLCV series |
| GET | `/{ts_code}/indicators` | Technical indicators |
| POST | `/{ts_code}/forecast` | Forecast job |

## Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | `{"status":"ok"}` |
