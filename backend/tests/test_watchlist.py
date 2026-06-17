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

    login = f"wl_{uuid.uuid4().hex[:8]}"
    client.post("/api/auth/register", json={"login": login, "password": "secret123"})
    res = client.post("/api/auth/login", json={"login": login, "password": "secret123"})
    return res.json()["access_token"]


MOCK_WATCHLIST = {
    "as_of_date": "2026-06-11",
    "items": [
        {
            "ts_code": "000001.SZ",
            "name": "平安银行",
            "industry": "银行",
            "quote": {"trade_date": "2026-06-11", "close": 12.5, "pct_chg": 1.2},
            "portfolios": ["pf1"],
        }
    ],
}


@patch("app.services.portfolio_service.PortfolioService.list_watchlist_with_quotes", return_value=MOCK_WATCHLIST)
def test_list_watchlist(mock_list, auth_token):
    headers = _auth_headers(auth_token)
    res = client.get("/api/portfolios/watchlist", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["as_of_date"] == "2026-06-11"
    assert data["items"][0]["ts_code"] == "000001.SZ"
    mock_list.assert_called_once()


def test_bulk_add_and_remove(auth_token):
    headers = _auth_headers(auth_token)
    client.post("/api/portfolios", json={"name": "wlpf"}, headers=headers)

    res = client.post(
        "/api/portfolios/wlpf/watchlist/bulk",
        headers=headers,
        json={"ts_codes": ["000001.SZ", "600519.SH"]},
    )
    assert res.status_code == 200
    assert "000001.SZ" in res.json()["follow_stocks"]
    assert "600519.SH" in res.json()["follow_stocks"]

    res2 = client.delete("/api/portfolios/wlpf/watchlist/000001.SZ", headers=headers)
    assert res2.status_code == 200
    assert "000001.SZ" not in res2.json()["follow_stocks"]
    assert "600519.SH" in res2.json()["follow_stocks"]


@patch(
    "app.services.portfolio_service.PortfolioService.list_portfolio_watchlist_with_quotes",
    return_value={
        "portfolio": "wlpf",
        "as_of_date": "2026-06-11",
        "items": [{"ts_code": "600519.SH", "name": "贵州茅台", "quote": {"trade_date": "2026-06-11", "close": 1700, "pct_chg": 0.5}}],
    },
)
def test_get_portfolio_watchlist(mock_list, auth_token):
    headers = _auth_headers(auth_token)
    res = client.get("/api/portfolios/wlpf/watchlist", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["portfolio"] == "wlpf"
    assert data["items"][0]["ts_code"] == "600519.SH"
    mock_list.assert_called_once_with("wlpf")
