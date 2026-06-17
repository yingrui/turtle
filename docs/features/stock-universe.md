# Market quotes (stock universe)

Browse the full A-share universe in `tushare.stock_basic`, with latest-day quotes from `tushare.stock_trade_daily`. Tables are **populated by an external ETL**; this app reads them only.

> Data is **daily close** — not real-time. The UI labels the as-of trade date on `/market` and stock detail pages.

## SPA

| Route | Page |
|-------|------|
| `/market` | Quote list (alias `/stocks/list`) |
| `/stocks/:tsCode` | Stock detail — quote bar, K-line, indicators |

### Quote list (`/market`)

- Search by code, name, or pinyin (`cnspell`)
- Exchange chips: SSE / SZSE / ChiNext / STAR / BSE
- Industry and listing-status filters; hide ST names
- **Industry movers** bar — circ-mv-weighted avg change%; click to filter by industry
- Sortable columns: code, name, OHLC, change%, volume, turnover, industry
- Filter state synced to URL query string (shareable bookmarks)
- Export current page to CSV
- Row click → `/stocks/:tsCode`
- **Watchlist** → add symbol to a portfolio `follow_stocks`

### Stock detail (`/stocks/:tsCode`)

- Header: name, code, industry, delayed-data label
- Quote strip: price, change%, open/high/low, volume, turnover
- Tabs: **K-line** (candlestick + volume) · **Indicators** (MA, Donchian, ATR, Bollinger)
- Links to forecast and watchlist

## vs screening

| | Market quotes | Screening |
|---|---------------|-----------|
| Purpose | Browse master data + latest quote | Strategy filter (trend, ADF) |
| Data | `stock_basic` + one day OHLCV | Engine / `PortfolioFilter` |
| Route | `/market`, `/stocks/:tsCode` | `/screening` |

## Roadmap

See [Product roadmap](../product-roadmap.md) for Phase 2+ (dedicated watchlist page, sparklines, performance).

## API

See [API reference — Stocks](api-reference.md#stocks-apistocks).
