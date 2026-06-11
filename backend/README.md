# Stock Trading Backend

FastAPI service for the stock trading system. Trading engine code lives in `app/core/`.

## Setup

```bash
cd backend && uv venv && source .venv/bin/activate
uv pip install -e .
cp .env.example .env
```

See [docs/features/configuration.md](../docs/features/configuration.md) and [docs/developer/setup.md](../docs/developer/setup.md).

## Run

```bash
cd backend && ./dev.sh
```

`dev.sh` loads env, runs `python -m alembic upgrade head`, starts uvicorn on **http://localhost:8200**.

## Tests

```bash
cd backend && pytest tests/
```
