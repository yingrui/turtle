import os
import sys

# Ensure stock-trading backend is imported, not another project on PYTHONPATH
_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

os.environ.setdefault("DB_URL", "sqlite:///./test_stock.db")
os.environ.setdefault("STOCK_LOGS_DIR", os.path.join(os.path.dirname(__file__), "../../logs"))

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
