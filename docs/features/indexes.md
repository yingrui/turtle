# Indexes

Index series from `tushare.index_daily`, for reading the market and for judging a backtest against it.

## SPA

**`/indexes`** — a list beside a chart:

- the list shows only indexes that **carry daily bars** (the feed has 10k names, ~76 have bars), the six
  broad benchmarks first; sortable by name/code/close/change, click a row to chart it;
- the chart is a candlestick with volume, over `3M / 6M / 1Y / 3Y`;
- the header repeats the selected index's close and change.

The home dashboard also renders a compact strip (`上证指数`, `深证成指`, `创业板指`, `沪深300`,
`中证500`, `中证1000`) — the market's own numbers above the portfolio's.

## Benchmark in a simulation

`/simulation/results` overlays an index on the equity curve: pick a benchmark and both series are
**rebased to 100 on the run's first day**, with the point difference shown next to the selector
(`相对基准：-9.13 点`). A return percentage alone cannot say whether a strategy beat the market;
two rebased lines can.

## API

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/indexes` | Indexes with daily bars, benchmarks first, with latest `close` and `pct_chg` |
| GET | `/api/indexes/{ts_code}/daily?start=&end=` | OHLC + `pct_chg`/`vol`/`amount` (default: last year) |
| GET | `/api/simulations/{run_id}/benchmark?ts_code=` | Equity vs index, both rebased to 100, plus `excess_pct` |

## Data

`tushare.index_basic` (metadata) and `tushare.index_daily` (bars, 2024-01 → now for the six
benchmarks) are written by the external ETL; migration `013` declares the contract the app reads and
is idempotent. A day the index did not trade keeps the previous close in a benchmark series rather
than breaking the line.
