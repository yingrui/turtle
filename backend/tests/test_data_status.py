from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, raise_server_exceptions=True)


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_token():
    import uuid

    login = f"ds_{uuid.uuid4().hex[:8]}"
    client.post("/api/auth/register", json={"login": login, "password": "secret123"})
    res = client.post("/api/auth/login", json={"login": login, "password": "secret123"})
    return res.json()["access_token"]


MOCK_STATUS = {
    "as_of_date": "2026-06-11",
    "source": "external_etl",
    "tables": [
        {"name": "stock_trade_daily", "latest_trade_date": "2026-06-11", "row_count": 1000},
        {"name": "daily_basic", "latest_trade_date": "2026-06-11", "row_count": 5000},
    ],
}


@patch("app.api.data.Dataset")
def test_data_status(mock_dataset_cls, auth_token):
    mock_dataset_cls.return_value.get_data_status.return_value = MOCK_STATUS
    headers = _auth_headers(auth_token)
    res = client.get("/api/data/status", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["as_of_date"] == "2026-06-11"
    assert data["source"] == "external_etl"
    assert len(data["tables"]) == 2


@patch("app.api.data.Dataset")
def test_latest_date_compat(mock_dataset_cls, auth_token):
    mock_dataset_cls.return_value.get_latest_date.return_value = "2026-06-11"
    headers = _auth_headers(auth_token)
    res = client.get("/api/data/latest-date", headers=headers)
    assert res.status_code == 200
    assert res.json()["latest_date"] == "2026-06-11"
