# Operations · Docker

Full stack: `docker/docker-compose.yml` — Postgres, backend, frontend (nginx).

## What runs

| Service | Image / build | Notes |
|---|---|---|
| `postgres` | `pgvector/pgvector:pg16` | Host **5433** → container 5432 (`STOCK_DATABASE_HOST_PORT`) |
| `backend` | `docker/Dockerfile` (`backend` target) | FastAPI on **8200**, internal only |
| `frontend` | `docker/Dockerfile.frontend` | nginx on host **3200** → proxies `/api` to backend |

## Bring it up

From repo root:

```bash
cp docker/.env.example docker/.env
# Set TUSHARE_TOKEN, STOCK_SECRET_KEY, etc.

docker compose -f docker/docker-compose.yml up -d --build
open http://localhost:3200
```

Tear down:

```bash
docker compose -f docker/docker-compose.yml down
```

## Environment

Compose reads `docker/.env`. Key variables:

| Variable | Purpose |
|---|---|
| `TUSHARE_TOKEN` | Market data sync |
| `STOCK_DATABASE_*` | Postgres credentials (defaults: `stock`/`stock`/`stock`) |
| `STOCK_SECRET_KEY` | JWT signing |
| `STOCK_ALLOW_SIGNUP` | First user becomes admin when `true` |

Inside Compose, `STOCK_DATABASE_HOST=postgres`. Backend runs `alembic upgrade head` on start (Dockerfile CMD).

## Volumes

- `stock_postgres_pg16` — database data
- `stock_logs` — simulation/job logs at `/app/logs`

## See also

- [Quickstart](../quickstart.md)
- [Architecture](../architecture.md)
- [Configuration](../features/configuration.md)
