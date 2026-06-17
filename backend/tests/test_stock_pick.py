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

    login = f"sp_{uuid.uuid4().hex[:8]}"
    client.post("/api/auth/register", json={"login": login, "password": "secret123"})
    res = client.post("/api/auth/login", json={"login": login, "password": "secret123"})
    return res.json()["access_token"]


MOCK_PICK = {
    "as_of_date": "2026-06-11",
    "total": 1,
    "items": [
        {
            "ts_code": "000001.SZ",
            "name": "平安银行",
            "industry": "银行",
            "pe_ttm": 5.2,
            "pb": 0.6,
            "circ_mv": 200000.0,
        }
    ],
}

MOCK_PRESETS = [
    {"id": "low_pe", "name": "低市盈率", "name_en": "Low PE", "params": {"pe_ttm_max": 20}},
]


@patch("app.services.stock_pick_service.stock_pick.pick_stocks", return_value=MOCK_PICK)
def test_stock_pick_api(mock_pick, auth_token):
    headers = _auth_headers(auth_token)
    res = client.post(
        "/api/stock-pick",
        headers=headers,
        json={"pe_ttm_max": 20, "limit": 100},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["ts_code"] == "000001.SZ"
    mock_pick.assert_called_once()


@patch("app.services.stock_pick_service.stock_pick.get_presets", return_value=MOCK_PRESETS)
def test_stock_pick_presets(mock_presets, auth_token):
    headers = _auth_headers(auth_token)
    res = client.get("/api/stock-pick/presets", headers=headers)
    assert res.status_code == 200
    assert len(res.json()["presets"]) == 1
    mock_presets.assert_called_once()
