#!/usr/bin/env python3
"""Ensure pgvector extension is available (`CREATE EXTENSION IF NOT EXISTS vector`).

Uses the same database URL as the FastAPI app (backend/.env).
Non-fatal when the server has no pgvector build (e.g. bare Postgres); Docker Compose uses pgvector/pgvector:pg16.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text

from app.config import settings


def main() -> int:
    print(
        "PostgreSQL target for pgvector check:",
        f"{settings.database_user}@{settings.database_host}:{settings.database_port}/{settings.database_name}",
        flush=True,
    )
    engine = create_engine(settings.db_url)
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.execute(text("SELECT '[1,2,3]'::vector <=> '[1,2,3]'::vector AS d"))
        print("pgvector OK: extension present and distance query succeeded.", flush=True)
        return 0
    except Exception as e:
        msg = str(e).lower()
        if "vector" in msg or "$libdir" in msg:
            print(
                "stock: pgvector not available on this PostgreSQL server (optional until vector features ship).",
                file=sys.stderr,
            )
            print(
                "  Docker: use pgvector/pgvector:pg16 (see docker/docker-compose.yml).",
                file=sys.stderr,
            )
            return 0
        raise


if __name__ == "__main__":
    sys.exit(main())
