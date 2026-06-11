import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, raise_server_exceptions=True)


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_token():
    import uuid

    login = f"pf_{uuid.uuid4().hex[:8]}"
    client.post("/api/auth/register", json={"login": login, "password": "secret123"})
    res = client.post("/api/auth/login", json={"login": login, "password": "secret123"})
    return res.json()["access_token"]


def test_portfolio_crud(auth_token):
    headers = _auth_headers(auth_token)
    create = client.post("/api/portfolios", json={"name": "testpf"}, headers=headers)
    assert create.status_code == 200
    assert create.json()["name"] == "testpf"
    assert create.json()["follow_stocks"] == []

    listed = client.get("/api/portfolios", headers=headers)
    assert "testpf" in listed.json()["portfolios"]

    save = client.put(
        "/api/portfolios/testpf",
        json={"config": {**create.json(), "follow_stocks": ["600519.SH"]}},
        headers=headers,
    )
    assert save.status_code == 200
    assert save.json()["follow_stocks"] == ["600519.SH"]

    delete = client.delete("/api/portfolios/testpf", headers=headers)
    assert delete.status_code == 200
