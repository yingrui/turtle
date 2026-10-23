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
| GET | `/status` | Table freshness (`latest_trade_date`, row counts); `source: external_etl` |
| GET | `/latest-date` | Latest trade date in `stock_trade_daily` (`null` if empty) |

## Stock pick — `/api/stock-pick`

| Method | Path | Description |
|--------|------|-------------|
| POST | `/` | Fundamental pick on `daily_basic` (sync) |
| GET | `/presets` | Built-in pick templates |

## Portfolios — `/api/portfolios`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | List portfolio names |
| GET | `/watchlist` | Aggregated watchlist across all portfolios (legacy) |
| GET | `/{name}/watchlist` | Watchlist stocks + quotes for one portfolio |
| POST | `/` | Create portfolio |
| GET | `/{name}` | Composed config dict (`follow_stocks`, `investments`, `risk_control`, `policies`) |
| GET | `/{name}/yaml` | Get YAML representation |
| PUT | `/{name}` | Update from a config dict (decomposed into tables) |
| PUT | `/{name}/yaml` | Update from YAML body |
| DELETE | `/{name}` | Delete portfolio |
| POST | `/{name}/watchlist` | Append `ts_code` to the portfolio's stocks |
| POST | `/{name}/watchlist/bulk` | Bulk append `{ ts_codes: [] }` |
| DELETE | `/{name}/watchlist/{ts_code}` | Remove symbol from the watchlist |
| GET | `/{name}/stocks` | Stocks of the portfolio with cost basis, realized P&L, risk fields; held positions also carry `current_price` / `market_value` / `unrealized_pnl` from the latest quote |
| POST | `/{name}/stocks` | Add a stock (`{ ts_code, … }`) |
| PATCH | `/{name}/stocks/{ts_code}` | Update status / target amount / stop loss / note |
| DELETE | `/{name}/stocks/{ts_code}` | Remove a stock (rejected when held or with trade history) |
| POST | `/{name}/stocks/{ts_code}/rebuild` | Recompute aggregates from the ledger |
| GET | `/{name}/transactions` | Ledger, filterable by `ts_code` / `simulation_run_id` |
| GET | `/{name}/equity` | Daily market value / cost basis rebuilt from the ledger (`?days=180`) |
| POST | `/{name}/transactions` | Record a buy/sell (`side`, `shares`, `price`, `trade_date`, …) |
| GET | `/{name}/risk-control` | Risk parameters (flattened engine keys) |
| PUT | `/{name}/risk-control` | Update risk parameters |
| GET | `/{name}/policies` | Ordered policies with parameters |
| PUT | `/{name}/policies` | Replace the policy list |
| GET | `/{name}/cash-flows` | Cash in/out records |
| POST | `/{name}/cash-flows` | Add a cash flow (`{ flow_date, amount, kind? }`) |

## Jobs — `/api/jobs`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | List jobs |
| GET | `/{job_id}` | Job detail |
| POST | `/` | Create job (`portfolio_screen`, `simulation`, `factor_compute`) |

`data_sync` / `calendar_sync` are **rejected** (400) — use external ETL.

### Simulation job body

`portfolio`, `start_date`, `end_date`, optional `policy_ids`, optional `ts_codes` (overrides `follow_stocks` for the run).

### Screening job body

`as_of_date`, optional `ignore_st`, optional `trend_filter` (`up` / `down`).

## Screening — `/api/screening`

| Method | Path | Description |
|--------|------|-------------|
| POST | `/` | Run screen (returns job or results) |

## Factors — `/api/factors`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Catalogue with coverage (`computable`, `category` filters) |
| GET | `/{code}` | One definition + coverage |
| GET | `/{code}/dates` | Dates that have values, newest first |
| GET | `/{code}/values` | Values — `ts_code` (history) or `trade_date` (cross-section), plus `start`/`end`/`sort`/`order`/`limit`/`offset` |
| POST | `/{code}/compute` | Start a `factor_compute` job for a window (`start`, `end`); 400 if the factor has no formula |

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
| GET | `/{ts_code}/snapshot` | Basic info + latest quote + `fundamentals` from `daily_basic` |
| GET | `/{ts_code}/ohlcv` | QFQ-adjusted OHLCV series (`?limit=250`, max 2000) |
| GET | `/{ts_code}/indicators` | Technical indicators |
| POST | `/{ts_code}/forecast` | Forecast job |

### `GET /universe` query parameters

`q`, `exchange` (SH/SZ/BJ), `market`, `industry`, `list_status` (default `L`), `exclude_st` (default `true`), `page`, `page_size`, `sort`, `order`.

Sort fields: `ts_code`, `name`, `industry`, `list_date`, `open`, `high`, `low`, `close`, `pct_chg`, `vol`, `amount`.

Quote object on each universe item: `open`, `high`, `low`, `close`, `pre_close`, `pct_chg`, `vol`, `amount`, `trade_date`.

Snapshot `fundamentals` (when `daily_basic` exists): `pe_ttm`, `pb`, `ps_ttm`, `circ_mv`, `total_mv`, `turnover_rate`, `limit_status`, etc.

## Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | `{"status":"ok","started_at":"<iso8601>"}` (worker boot time; useful after hot reload) |
| POST | `/-/reload` | Dev/test only — bumps a sentinel so `uvicorn --reload` restarts; `{"ok":true,"sentinel":"…"}` |

## Webhooks (inbound, openKMS → turtle)

| Method | Path | Notes |
|--------|------|-------|
| POST | `/api/webhooks/openkms/portfolio-changes` | Apply proposed holding changes from the ontology. Signed: `X-OpenKMS-Signature: sha256=HMAC(secret, raw body)`, verified in constant time; **503** when `STOCK_OPENKMS_WEBHOOK_SECRET` is unset, **401** on a bad signature. Body is **either** `{"changes": [{id, action, portfolio_id, ts_code, target_weight?, target_status?}]}` **or** an openKMS Action envelope `{"event": "action.executed", "object": {"object_type": "Holding", "properties": {…}}, "input": {…}}` — the second mirrors a Holding an Action just edited, writing only the fields the Action's `input` names (never `hold_shares`). Anything else is refused, `action ∈ add \| remove \| set_weight \| set_status`. Applied through `PortfolioService`, so `hold_shares` / `avg_cost` stay ledger aggregates; a position with holdings or history is **closed**, not deleted. Idempotent per change. Returns `{applied, failed, results: [{id, ok, error?}]}` — one bad change does not fail the batch. When anything was applied it asks openKMS to re-index `STOCK_OPENKMS_REINDEX` (off-request, best-effort), so the ontology's mirror catches up. |
