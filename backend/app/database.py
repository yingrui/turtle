from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


def _engine_kwargs() -> dict:
    kwargs: dict = {"pool_pre_ping": True, "pool_size": 10, "max_overflow": 10, "pool_recycle": 1800}
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
