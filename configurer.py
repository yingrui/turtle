import os

import tushare as ts
import yaml
from dotenv import load_dotenv
from sqlalchemy import create_engine


def get_sql_connection():
    load_dotenv()
    engine = create_engine(os.getenv('DB_URL'), encoding="utf8")
    return engine.connect()


def get_connection_pool():
    load_dotenv()
    return create_engine(os.getenv('DB_URL'), encoding="utf8")


def get_ts_api():
    load_dotenv()
    return ts.pro_api(token=os.getenv('TUSHARE_TOKEN'))


def load_yaml(file):
    with open(file, 'r') as stream:
        try:
            return yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(exc)
