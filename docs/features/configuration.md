# Configuration

Canonical source: `backend/app/config.py`. Ready-to-edit example: `backend/.env.example` (local) and `docker/.env.example` (Compose).

`backend/dev.sh` loads, in order: repo root `.env`, `docker/.env`, then `backend/.env` (first file found wins for each variable when sourced).

## Database

| Variable | Default | Purpose |
|---|---|---|
| `STOCK_DATABASE_HOST` | `localhost` | PostgreSQL host |
| `STOCK_DATABASE_PORT` | `5432` | Port |
| `STOCK_DATABASE_USER` | `stock` | DB user |
| `STOCK_DATABASE_PASSWORD` | `stock` | Password |
| `STOCK_DATABASE_NAME` | `stock` | Database name |
| `DB_URL` | *(unset)* | Optional full SQLAlchemy URL override (e.g. SQLite for tests) |

Compose sets host to `postgres` inside the stack via `docker-compose.yml`.

## Authentication (local mode)

| Variable | Default | Purpose |
|---|---|---|
| `STOCK_AUTH_MODE` | `local` | Only `local` is implemented |
| `STOCK_ALLOW_SIGNUP` | `true` | Self-registration; **first** user is admin |
| `STOCK_LOCAL_JWT_EXP_HOURS` | `168` | JWT lifetime |
| `STOCK_SECRET_KEY` | dev placeholder | HS256 signing — **rotate in production** |
| `STOCK_FRONTEND_URL` | `http://localhost:3200` | CORS allowed origin |

## Tushare

| Variable | Default | Purpose |
|---|---|---|
| `TUSHARE_TOKEN` | empty | API token for market data sync |

Required for data collection jobs. Set in `backend/.env` or `docker/.env`.

## Paths

| Variable | Default | Purpose |
|---|---|---|
| `STOCK_LOGS_DIR` | `/app/logs` (Docker) or `../logs` via `dev.sh` | Simulation and job log files |

Portfolios are stored in PostgreSQL (`portfolios` table), not YAML files on disk.

## pgvector

The Postgres image is `pgvector/pgvector:pg16`. `backend/scripts/ensure_pgvector.py` runs `CREATE EXTENSION IF NOT EXISTS vector` on startup (`dev.sh` / Docker CMD). Vector features are reserved for future use; the extension is installed proactively.
