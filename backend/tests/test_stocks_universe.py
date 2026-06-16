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

    login = f"su_{uuid.uuid4().hex[:8]}"
    client.post("/api/auth/register", json={"login": login, "password": "secret123"})
    res = client.post("/api/auth/login", json={"login": login, "password": "secret123"})
    return res.json()["access_token"]


MOCK_UNIVERSE = {
    "total": 2,
    "page": 0,
    "page_size": 50,
    "as_of_date": "2026-06-11",
    "items": [
        {
            "ts_code": "000001.SZ",
            "symbol": "000001",
            "name": "平安银行",
            "industry": "银行",
            "market": "主板",
            "area": "深圳",
            "exchange": "SZ",
            "list_status": "L",
            "list_date": "19910403",
            "quote": {
                "trade_date": "2026-06-11",
                "open": 12.3,
                "high": 12.8,
                "low": 12.1,
                "close": 12.5,
                "pre_close": 12.35,
                "pct_chg": 1.2,
                "vol": 1000.0,
                "amount": 5000.0,
            },
        },
        {
            "ts_code": "600519.SH",
            "symbol": "600519",
            "name": "贵州茅台",
            "industry": "白酒",
            "market": "主板",
            "area": "贵州",
            "exchange": "SH",
            "list_status": "L",
            "list_date": "20010827",
            "quote": None,
        },
    ],
}

MOCK_META = {
    "latest_trade_date": "2026-06-11",
    "listed_count": 5000,
    "exchanges": {"SH": 2100, "SZ": 2800, "BJ": 200},
    "markets": ["主板", "创业板"],
    "industries": ["银行", "白酒"],
}

MOCK_SEARCH = [
    {"ts_code": "000001.SZ", "name": "平安银行", "industry": "银行", "exchange": "SZ"},
]

MOCK_INDUSTRY = {
    "as_of_date": "2026-06-11",
    "weight_by": "circ_mv",
    "items": [
        {"industry": "银行", "stock_count": 40, "avg_pct_chg": 0.8, "up_count": 25, "down_count": 15, "total_circ_mv": 1.2e6},
    ],
}

MOCK_SNAPSHOT = MOCK_UNIVERSE["items"][0]


@patch("app.services.stock_service.stock_universe.list_universe", return_value=MOCK_UNIVERSE)
def test_universe_list(mock_list, auth_token):
    headers = _auth_headers(auth_token)
    res = client.get("/api/stocks/universe?page=0&sort=pct_chg&order=desc", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 2
    assert data["items"][0]["ts_code"] == "000001.SZ"
    assert data["as_of_date"] == "2026-06-11"
    mock_list.assert_called_once()


@patch("app.services.stock_service.stock_universe.get_universe_meta", return_value=MOCK_META)
def test_universe_meta(mock_meta, auth_token):
    headers = _auth_headers(auth_token)
    res = client.get("/api/stocks/universe/meta", headers=headers)
    assert res.status_code == 200
    assert res.json()["listed_count"] == 5000
    mock_meta.assert_called_once()


@patch("app.services.stock_service.stock_universe.get_industry_summary", return_value=MOCK_INDUSTRY)
def test_industry_summary(mock_summary, auth_token):
    headers = _auth_headers(auth_token)
    res = client.get("/api/stocks/universe/industry-summary", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["as_of_date"] == "2026-06-11"
    assert data["items"][0]["industry"] == "银行"
    mock_summary.assert_called_once()


@patch("app.services.stock_service.stock_universe.get_stock_snapshot", return_value=MOCK_SNAPSHOT)
def test_stock_snapshot(mock_snap, auth_token):
    headers = _auth_headers(auth_token)
    res = client.get("/api/stocks/000001.SZ/snapshot", headers=headers)
    assert res.status_code == 200
    assert res.json()["ts_code"] == "000001.SZ"
    mock_snap.assert_called_once_with("000001.SZ")


@patch("app.services.stock_service.stock_universe.get_stock_snapshot", return_value=None)
def test_stock_snapshot_not_found(mock_snap, auth_token):
    headers = _auth_headers(auth_token)
    res = client.get("/api/stocks/INVALID/snapshot", headers=headers)
    assert res.status_code == 404


@patch("app.services.stock_service.stock_universe.search_stocks", return_value=MOCK_SEARCH)
def test_search_stocks(mock_search, auth_token):
    headers = _auth_headers(auth_token)
    res = client.get("/api/stocks/search?q=平安", headers=headers)
    assert res.status_code == 200
    assert len(res.json()["stocks"]) == 1
    mock_search.assert_called_once()


def test_add_watchlist(auth_token):
    headers = _auth_headers(auth_token)
    client.post("/api/portfolios", json={"name": "watchpf"}, headers=headers)
    res = client.post(
        "/api/portfolios/watchpf/watchlist",
        json={"ts_code": "000001.SZ"},
        headers=headers,
    )
    assert res.status_code == 200
    assert "000001.SZ" in res.json()["follow_stocks"]

    res2 = client.post(
        "/api/portfolios/watchpf/watchlist",
        json={"ts_code": "000001.SZ"},
        headers=headers,
    )
    assert res2.json()["follow_stocks"].count("000001.SZ") == 1
