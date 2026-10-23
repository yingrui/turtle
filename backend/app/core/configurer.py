import os
from functools import lru_cache

import tushare as ts
import yaml
from sqlalchemy import create_engine


def _db_url() -> str:
    from app.config import settings

    return settings.db_url


@lru_cache(maxsize=1)
def _engine():
    """One process-wide engine for market-data reads.

    Creating an engine per query leaks a connection pool per call: `engine.connect()` checks a
    connection out and the throwaway engine never returns it, so a few hundred requests exhaust
    PostgreSQL's connection slots. The pool below is deliberately small — these are read-only,
    short queries.
    """
    url = _db_url()
    kwargs = {"pool_size": 5, "max_overflow": 5, "pool_pre_ping": True, "pool_recycle": 1800}
    if url.startswith("postgresql"):
        # Makes these connections identifiable in pg_stat_activity.
        kwargs["connect_args"] = {"application_name": "turtle-market"}
    return create_engine(url, **kwargs)


def get_connection_pool():
    return _engine()


def get_sql_connection():
    return _engine().connect()


def get_ts_api():
    from app.config import settings

    token = settings.tushare_token or os.getenv("TUSHARE_TOKEN", "")
    return ts.pro_api(token=token)


def load_yaml(file):
    with open(file, "r") as stream:
        try:
            return yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(exc)
