# Quickstart

Two paths: **Docker** (full stack) or **host** (backend + frontend on the machine, Postgres via Compose or external).

## Prerequisites

- **Docker** (Compose v2) for either path
- **Host path:** Python 3.11+, Node.js 20+, npm; [uv](https://github.com/astral-sh/uv) recommended for the backend venv
- **Tushare token** — required for market data sync ([tushare.pro](https://tushare.pro))

## Option A — Everything in Docker

```bash
cp docker/.env.example docker/.env
# Edit TUSHARE_TOKEN and DB secrets if needed

docker compose -f docker/docker-compose.yml up -d --build
open http://localhost:3200
```

Register the first user — they become **admin** automatically (`STOCK_ALLOW_SIGNUP=true` by default).

Ports and env overrides: [Operations · Docker](operations/docker.md).

## Option B — Backend and frontend on the host

```bash
# 1. Postgres (Compose only, or use your own instance)
docker compose -f docker/docker-compose.yml up -d postgres

# 2. Backend env
cp backend/.env.example backend/.env
# Set STOCK_DATABASE_* and TUSHARE_TOKEN

# 3. Backend (terminal 1)
cd backend && ./dev.sh

# 4. Frontend (terminal 2)
cd frontend && npm install && npm run dev
```

Open **http://localhost:3200**. Vite proxies `/api` to **http://localhost:8200**.

Use the backend venv for Alembic — not the system `alembic` binary (see [Developer setup](developer/setup.md#alembic)).

## After it's running

| Action | URL |
|---|---|
| SPA | <http://localhost:3200> |
| Backend OpenAPI | <http://localhost:8200/docs> |
| Health | <http://localhost:8200/health> |

1. **Data** — run a market data sync job (needs `TUSHARE_TOKEN`)
2. **Portfolio** — create a portfolio config in the UI
3. **Simulation** — start a backtest job and view results

## Tests

```bash
cd backend && source .venv/bin/activate && pytest tests/
```
