import os

import tushare as ts
import yaml
from sqlalchemy import create_engine


def _db_url() -> str:
    from app.config import settings

    return settings.db_url


def get_sql_connection():
    return create_engine(_db_url()).connect()


def get_connection_pool():
    return create_engine(_db_url())


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
