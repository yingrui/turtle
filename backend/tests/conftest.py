import os

import pytest

os.environ.setdefault("DB_URL", "sqlite:///./test_stock.db")
os.environ.setdefault("STOCK_SECRET_KEY", "test-secret")
os.environ.setdefault("STOCK_LOGS_DIR", os.path.join(os.path.dirname(__file__), "../../logs"))


@pytest.fixture(scope="session", autouse=True)
def _create_db_schema():
    from app.database import Base, engine

    Base.metadata.create_all(bind=engine)
    yield
