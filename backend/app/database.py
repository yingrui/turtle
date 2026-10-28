from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


def _engine_kwargs() -> dict:
    # Sized for a shared PostgreSQL that also serves MLflow, Keycloak and openKMS: `uvicorn --reload`
    # imports the app in the supervisor *and* the worker, so every pool exists twice. 100 slots shared
    # by four applications does not leave room for 10+10 twice per process.
    kwargs: dict = {
        "pool_pre_ping": True,
        "pool_size": 5,
        "max_overflow": 5,
        "pool_recycle": 1800,
        "pool_timeout": 10,
    }
    if settings.db_url.startswith("postgresql"):
        kwargs["connect_args"] = {"application_name": "turtle-app"}
    return kwargs


engine = create_engine(settings.db_url, **_engine_kwargs())
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
