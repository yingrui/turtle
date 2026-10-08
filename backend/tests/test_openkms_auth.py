"""STOCK_AUTH_MODE=none — identity from openKMS proxy headers."""

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _force_none_mode(monkeypatch):
    monkeypatch.setattr(settings, "stock_auth_mode", "none")


def test_me_anonymous_without_headers():
    r = client.get("/api/auth/me")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "anonymous"
    assert body["login"] == "anonymous"
    assert body["is_admin"] is True


def test_me_from_openkms_headers():
    r = client.get(
        "/api/auth/me",
        headers={
            "X-Openkms-User-Id": "11dcdd51-b251-4a69-9288-05ab2952be38",
            "X-Openkms-Username": "yingrui",
            "X-Openkms-User-Name": "Yingrui%20Feng",
            "X-Openkms-User-Email": "yingrui.f@gmail.com",
            "X-Openkms-User-Admin": "true",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "11dcdd51-b251-4a69-9288-05ab2952be38"
    assert body["login"] == "yingrui"
    assert body["name"] == "Yingrui Feng"
    assert body["email"] == "yingrui.f@gmail.com"
    assert body["is_admin"] is True


def test_api_uses_openkms_identity_without_bearer():
    r = client.get(
        "/api/portfolios",
        headers={
            "X-Openkms-User-Id": "u-1",
            "X-Openkms-Username": "alice",
            "X-Openkms-User-Name": "Alice",
            "X-Openkms-User-Admin": "false",
        },
    )
    assert r.status_code == 200
    assert "portfolios" in r.json()
