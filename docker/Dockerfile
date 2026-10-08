ARG BACKEND_BASE=turtle-backend-base:latest
FROM ${BACKEND_BASE}

WORKDIR /app/backend

COPY backend/app /app/backend/app
COPY backend/alembic /app/backend/alembic
COPY backend/alembic.ini /app/backend/alembic.ini
COPY backend/scripts /app/backend/scripts
COPY backend/pyproject.toml /app/backend/pyproject.toml

# Deps already in the base image; this only registers the local package.
RUN pip install --no-cache-dir --no-deps -e .

EXPOSE 8200

HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=5 \
    CMD curl -sf http://127.0.0.1:8200/health > /dev/null || exit 1

CMD ["sh", "-c", "python scripts/ensure_pgvector.py && alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8200"]
