# 股票交易系统

**Personal stock trading system** — backtest, screen, and analyze Chinese A-shares (MA, Donchian, Bollinger, ensemble, ATR policies).

The web app replaces the old Streamlit UI: React SPA + FastAPI backend + PostgreSQL (market data in schema **`tushare`**, portfolios and simulation results in **`public`**).

[Quickstart](quickstart.md){ .md-button .md-button--primary }

---

## What the system does

| Surface | Role |
|---------|------|
| **Market data** | Read from PostgreSQL `tushare` (written by **external ETL**) |
| **Portfolios** | Create and edit portfolio config in the UI (stored as JSON in `portfolios`) |
| **Stock picking (选股)** | Factor / rule-based screens on synced market data |
| **Factor analysis (因子)** | Planned: factor library, cross-section ranks, IC (see [research](research/07-factor-and-stock-selection.md)) |
| **Simulation** | Backtest a portfolio + policy over a date range; persist daily equity and trades |
| **Stock analysis** | OHLCV charts, indicators, and forecast for a single symbol |
| **Jobs** | Background tasks for **screening, factor compute, simulation** (not data sync) |

North star: a personal quant research loop — **pick stocks with factors → backtest → review** — not a data pipeline or brokerage.

## Where to start

| If you want to… | Read |
|---|---|
| See product gaps & roadmap | [Product roadmap](product-roadmap.md) |
| Deep-dive what to build next | [Research](research/README.md)（中文） |
| Run locally (Docker or host) | [Quickstart](quickstart.md) |
| Understand the stack | [Architecture](architecture.md) |
| Find a feature or API route | [Functionalities](functionalities.md) → `features/*.md` |
| Environment variables | [Configuration](features/configuration.md) |
| Database tables | [Data models](features/data-models.md) |
| HTTP reference | [API reference](features/api-reference.md) |
| Host dev setup (venv, Alembic, pgvector) | [Developer setup](developer/setup.md) |
| Docker deployment | [Operations · Docker](operations/docker.md) |
| Frontend tokens and SCSS | [Design system](design-system.md) |

## At a glance

```mermaid
flowchart LR
  User([Browser]) -->|nginx 3200 / Vite dev| FE[React SPA]
  FE -->|/api| BE[FastAPI · 8200]
  BE --> PG[(PostgreSQL + pgvector)]
  BE --> TS[Tushare API]
```

| Service | Default port |
|---|---|
| Frontend (Docker, nginx) | **3200** |
| Frontend (Vite dev) | **3200** (proxies `/api` → backend) |
| Backend (FastAPI) | **8200** |
| PostgreSQL | **5432** (host or Compose internal) |

## Project layout

| Path | What's inside |
|---|---|
| `backend/` | FastAPI API, trading engine (`app/core/`), Alembic, JWT auth |
| `frontend/` | React 19 + Vite SPA (openKMS-derived design system) |
| `docker/` | Dockerfiles and `docker-compose.yml` |
| `docs/` | This documentation site |
