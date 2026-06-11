FROM python:3.12-slim-bookworm AS base

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml /app/backend/pyproject.toml
COPY backend/app /app/backend/app
COPY backend/alembic /app/backend/alembic
COPY backend/alembic.ini /app/backend/alembic.ini
COPY backend/scripts /app/backend/scripts
WORKDIR /app/backend
RUN pip install --no-cache-dir -e .

ENV PYTHONPATH=/app/backend
ENV STOCK_LOGS_DIR=/app/logs

RUN mkdir -p /app/logs

FROM base AS backend

WORKDIR /app/backend

EXPOSE 8200

HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=5 \
    CMD curl -sf http://127.0.0.1:8200/health > /dev/null || exit 1

CMD ["sh", "-c", "python scripts/ensure_pgvector.py && alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8200"]
