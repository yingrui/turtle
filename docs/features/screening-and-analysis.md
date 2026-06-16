# Screening & stock analysis

## Screening

Route: **`/screening`**

Runs policy-based filters over synced market data. API: `POST /api/screening`. Implementation: `app/services/screening_service.py` + engine policies under `app/core/engine/policy/`.

## Market quotes

Route: **`/market`**

Browse all listed stocks with latest-day quotes. See [Stock universe](stock-universe.md).

## Stock analysis

Route: **`/stocks`** (deep link: `?ts_code=600519.SH`)

Search symbols, view OHLCV charts and indicators for a `ts_code`. Data from `tushare` tables via `app/services/stock_service.py`.

## Forecast

Route: **`/forecast`**

`POST /api/stocks/{ts_code}/forecast` triggers a forecast job; results displayed in the UI.

Charts use **Apache ECharts** via `frontend/src/components/Chart.tsx`.
