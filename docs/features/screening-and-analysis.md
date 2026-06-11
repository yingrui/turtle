# Screening & stock analysis

## Screening

Route: **`/screening`**

Runs policy-based filters over synced market data. API: `POST /api/screening`. Implementation: `app/services/screening_service.py` + engine policies under `app/core/engine/policy/`.

## Stock analysis

Route: **`/stocks`**

Search symbols, view OHLCV charts and indicators for a `ts_code`. Data from `tushare` tables via `app/services/stock_service.py`.

## Forecast

Route: **`/forecast`**

`POST /api/stocks/{ts_code}/forecast` triggers a forecast job; results displayed in the UI.

Charts use **Apache ECharts** via `frontend/src/components/Chart.tsx`.
