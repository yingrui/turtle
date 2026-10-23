import os
import tempfile
from pathlib import Path

import pytest

# Tests run on a throwaway sqlite file — never on the developer's PostgreSQL database.
_TMP_DIR = Path(tempfile.mkdtemp(prefix="turtle-tests-"))
os.environ["DB_URL"] = f"sqlite:///{_TMP_DIR / 'test_stock.db'}"
os.environ.setdefault("STOCK_SECRET_KEY", "test-secret")
# Keep local JWT for tests that register/login; runtime default is none (openKMS iframe).
os.environ.setdefault("STOCK_AUTH_MODE", "local")
os.environ.setdefault("STOCK_LOGS_DIR", os.path.join(os.path.dirname(__file__), "../../logs"))

# The engine queries `tushare.<table>`; sqlite has no schemas, so point the schema name at
# sqlite's main database. Must happen before any app module imports the schema constant.
from app.core import tushare_schema  # noqa: E402

tushare_schema.TUSHARE_SCHEMA = "main"


@pytest.fixture(scope="session", autouse=True)
def _create_db_schema():
    from app import models  # noqa: F401  (registers every table on Base.metadata)
    from app.database import Base, engine

    Base.metadata.create_all(bind=engine)
    from fixtures.market_data import seed  # tests/ is on sys.path

    with engine.begin() as conn:
        seed(conn)
    yield


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
