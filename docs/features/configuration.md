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

## Authentication

| Variable | Default | Purpose |
|---|---|---|
| `STOCK_AUTH_MODE` | `none` | `none` = openKMS proxy identity headers (no in-app login); `local` = username/password JWT |
| `STOCK_ALLOW_SIGNUP` | `true` | Self-registration when mode is `local`; **first** user is admin |
| `STOCK_LOCAL_JWT_EXP_HOURS` | `168` | JWT lifetime (`local` only) |
| `STOCK_OPENKMS_WEBHOOK_SECRET` | — | Shared secret the openKMS Function signs `POST /api/webhooks/openkms/portfolio-changes` with (`X-OpenKMS-Signature: sha256=…`). **Unset closes the endpoint (503)** — it never falls open. |
| `STOCK_OPENKMS_BASE_URL` | — | openKMS origin, used to ask for a re-index after a simulation run |
| `STOCK_OPENKMS_API_KEY` | — | Personal API key for that callback (needs object-type write on the Simulation type) |
| `STOCK_OPENKMS_SIMULATION_TYPE_ID` | — | Object type id of the ontology's `Simulation` |
| `STOCK_OPENKMS_NEO4J_DATA_SOURCE_ID` | — | Neo4j data source the re-index targets |
| `STOCK_OPENKMS_SIMULATION_LINK_TYPE_ID` | — | `simulationOf` link type — a new run needs its node **and** edge indexed |

All five are optional: unset, the app behaves exactly as before — proposals are refused (503) and no callback is sent.
| `STOCK_SECRET_KEY` | dev placeholder | HS256 signing for `local` — **rotate if using local** |
| `STOCK_FRONTEND_URL` | `http://localhost:3200` | CORS allowed origin |

See [Auth](auth.md).

## Tushare

| Variable | Default | Purpose |
|---|---|---|
| `TUSHARE_TOKEN` | empty | **Optional / legacy.** Market data is loaded by external ETL; this app does not sync from Tushare. |

## Paths

| Variable | Default | Purpose |
|---|---|---|
| `STOCK_LOGS_DIR` | `/app/logs` (Docker) or `../logs` via `dev.sh` | Simulation and job log files |

Portfolios are stored in PostgreSQL (`portfolios` table), not YAML files on disk.

## pgvector

The Postgres image is `pgvector/pgvector:pg16`. `backend/scripts/ensure_pgvector.py` runs `CREATE EXTENSION IF NOT EXISTS vector` on startup (`dev.sh` / Docker CMD). Vector features are reserved for future use; the extension is installed proactively.
