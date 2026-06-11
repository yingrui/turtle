# Data sync

Market data is fetched from **Tushare** and written to PostgreSQL schema **`tushare`**.

## SPA

- **`/data`** — trigger sync jobs, view latest date
- **`/jobs`** — poll job status and logs

## Jobs

Create via `POST /api/jobs` with a payload specifying sync type and date range. Jobs run in FastAPI background tasks; progress is stored in the `jobs` table.

Requires `TUSHARE_TOKEN` in the environment.

## Tables

See [Data models — tushare schema](data-models.md#tushare-schema-market-data).

Sync implementation: `app/core/dataset/sync.py` (uses `to_sql(..., schema=TUSHARE_SCHEMA)`).
