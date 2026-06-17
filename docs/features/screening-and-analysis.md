# Screening, factors & stock analysis

## Stock picking (选股中心)

Route: **`/screening`**

| Tab | Engine | API |
|-----|--------|-----|
| **基本面** | `daily_basic` filters (PE, PB, cap, turnover) | `POST /api/stock-pick` (sync) |
| **技术筛选** | Trend + ADF (`PortfolioFilter`) | `POST /api/jobs` → `portfolio_screen` (async) |

Results: link to `/stocks/:tsCode`, add to portfolio watchlist (`POST …/watchlist/bulk`), or send to backtest (`simulation` job with `ts_codes`).

See [Stock picking](stock-pick.md) and [Factor research](../research/07-factor-and-stock-selection.md).

## Watchlist

Route: **`/watchlist`**

Aggregated `follow_stocks` across portfolios with latest quotes: `GET /api/portfolios/watchlist`.

## Factor analysis (因子)

**Planned** — dedicated `/factor` page and `factor_values` table (Phase 3).

## Market quotes

Routes: **`/market`**, **`/stocks/:tsCode`**

Universe list, industry summary, K-line charts. Snapshot includes `fundamentals` from `daily_basic`.

## Stock analysis & forecast

Routes: **`/stocks`**, **`/forecast`**

Indicators and ARIMA forecast for a single symbol. Data is **read from `tushare`** (populated externally).

Charts: **Apache ECharts** — `frontend/src/components/Chart.tsx`.

## Data

This app **does not sync** market data. See [External data contract](data-sync.md) and **`/data`** (read-only status).
