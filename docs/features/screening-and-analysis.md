# Screening, factors & stock analysis

## Stock picking (选股中心)

Route: **`/screening`**

| Tab | Engine | API |
|-----|--------|-----|
| **基本面** | `daily_basic` filters (PE, PB, cap, turnover) | `POST /api/stock-pick` (sync) |
| **技术筛选** | Trend + ADF (`PortfolioFilter`) | `POST /api/jobs` → `portfolio_screen` (async) |

Results: link to `/stocks/:tsCode`, add to the portfolio (`POST …/watchlist/bulk`), **buy directly**
(opens the shared trade drawer → `POST …/transactions`; a symbol that is not in the portfolio yet is
created as a holding automatically), or send to backtest (`simulation` job with `ts_codes`).

See [Stock picking](stock-pick.md) and [Factor research](../research/07-factor-and-stock-selection.md).

## Watchlist

Route: **`/watchlist`**

Aggregated `follow_stocks` across portfolios with latest quotes: `GET /api/portfolios/watchlist`.

## Factor analysis (因子)

Implemented — see [Factors](factors.md) for the `/factor` catalogue, formulas, coverage and values.


## Market quotes

Routes: **`/market`**, **`/stocks/:tsCode`**

Universe list, industry summary, K-line charts. Snapshot includes `fundamentals` from `daily_basic`.

## Stock analysis & forecast

Route: **`/stocks/:tsCode`** — one page with four tabs: **K线 / 指标 / 因子 / 预测**. Indicators
(`ma`, `donchian`, `atr`, `bolling`, `distribution`) and the ARIMA forecast live here instead of on
separate pages; the old `/stocks` and `/forecast` routes redirect to `/market`. Data is **read from
`tushare`** (populated externally), factor values come from `factor_values`.

Charts: **Apache ECharts** — `frontend/src/components/Chart.tsx`.

## Data

This app **does not sync** market data. See [External data contract](data-sync.md) and **`/data`** (read-only status).
