# Developer setup

## Overview

- **Backend** (`backend/`): FastAPI + SQLAlchemy + Alembic; trading engine in `app/core/`
- **Frontend** (`frontend/`): React/Vite; `frontend/src/index.scss` loads design-system `_css-variables`, `_global`, `_utilities`. See [Design system](../design-system.md).

## Python environment

```bash
cd backend
uv venv && source .venv/bin/activate
uv pip install -e .
# or: pip install -e .
```

Copy env:

```bash
cp .env.example .env
```

## PostgreSQL

### Docker (recommended for dev)

```bash
docker compose -f docker/docker-compose.yml up -d postgres
```

Image: `pgvector/pgvector:pg16`. Match `STOCK_DATABASE_*` in `backend/.env`.

### Manual database creation

```sql
CREATE USER stock WITH PASSWORD 'stock';
CREATE DATABASE stock OWNER stock;
\c stock
CREATE EXTENSION IF NOT EXISTS vector;
```

PostgreSQL 15+ — ensure the app user owns or can use `public`:

```sql
ALTER SCHEMA public OWNER TO stock;
```

### External Postgres (e.g. existing `stock` DB)

Set `STOCK_DATABASE_*` in `.env`. After migrations, grant `tushare` schema access — see [Data models](../features/data-models.md#grants-external-postgres).

## Alembic

Always run migrations with the **backend venv**, not the system `alembic`:

```bash
cd backend
source .venv/bin/activate
python -m alembic upgrade head
python -m alembic current
```

`dev.sh` does this automatically. `alembic/env.py` prepends the backend directory to `sys.path` so another installed `app` package (e.g. openKMS) is not imported by mistake.

## Run backend

```bash
cd backend && ./dev.sh
```

Starts uvicorn on **http://localhost:8200** with reload.

## Run frontend

```bash
cd frontend && npm install && npm run dev
```

**http://localhost:3200** — Vite proxies `/api` to port 8200 (`frontend/vite.config.ts`).

## Tests

```bash
cd backend && source .venv/bin/activate && pytest tests/
```

## Frontend design system

Core SCSS was copied from [openKMS](https://github.com/yingrui/openKMS) `frontend/src/styles/design-system/`. See [Design system](../design-system.md) for what is included vs omitted.
