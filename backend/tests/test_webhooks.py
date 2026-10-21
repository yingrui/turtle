"""The openKMS → turtle door: signed, idempotent, and respectful of the ledger."""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models.portfolio import Portfolio, PortfolioStock

client = TestClient(app, raise_server_exceptions=True)
SECRET = "test-webhook-secret"
PATH = "/api/webhooks/openkms/portfolio-changes"


def _sign(body: bytes, secret: str = SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.fixture
def webhook_secret(monkeypatch):
    monkeypatch.setattr(settings, "stock_openkms_webhook_secret", SECRET)
    return SECRET


@pytest.fixture
def portfolio_id():
    import uuid

    db = SessionLocal()
    try:
        portfolio = Portfolio(name=f"webhook-pf-{uuid.uuid4().hex[:6]}", initial_investment=100000)
        db.add(portfolio)
        db.commit()
        return portfolio.id
    finally:
        db.close()


def _post(payload: dict, secret: str | None = SECRET):
    body = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if secret is not None:
        headers["X-OpenKMS-Signature"] = _sign(body, secret)
    return client.post(PATH, content=body, headers=headers)


def test_unconfigured_secret_does_not_open_the_endpoint(monkeypatch):
    monkeypatch.setattr(settings, "stock_openkms_webhook_secret", "")
    res = _post({"changes": []})
    assert res.status_code == 503


def test_a_bad_signature_is_rejected(webhook_secret, portfolio_id):
    res = _post({"changes": [{"id": "c1", "action": "add", "portfolio_id": portfolio_id, "ts_code": "600866.SH"}]}, secret="wrong")
    assert res.status_code == 401


def test_missing_signature_is_rejected(webhook_secret, portfolio_id):
    res = _post({"changes": []}, secret=None)
    assert res.status_code == 401


def test_add_creates_a_watching_row_and_repeats_are_idempotent(webhook_secret, portfolio_id):
    payload = {"changes": [{"id": "c1", "action": "add", "portfolio_id": portfolio_id, "ts_code": "600866.SH"}]}
    first = _post(payload)
    assert first.status_code == 200
    assert first.json()["applied"] == 1
    second = _post(payload)
    assert second.json()["applied"] == 1

    db = SessionLocal()
    try:
        rows = db.query(PortfolioStock).filter(PortfolioStock.portfolio_id == portfolio_id).all()
        assert [(r.ts_code, r.status) for r in rows] == [("600866.SH", "watching")]
    finally:
        db.close()


def test_set_weight_updates_only_the_planning_field(webhook_secret, portfolio_id):
    _post({"changes": [{"id": "c1", "action": "add", "portfolio_id": portfolio_id, "ts_code": "600866.SH"}]})
    res = _post(
        {
            "changes": [
                {
                    "id": "c2",
                    "action": "set_weight",
                    "portfolio_id": portfolio_id,
                    "ts_code": "600866.SH",
                    "target_weight": 0.08,
                }
            ]
        }
    )
    assert res.json()["applied"] == 1
    db = SessionLocal()
    try:
        row = db.query(PortfolioStock).filter(PortfolioStock.portfolio_id == portfolio_id).one()
        assert float(row.target_weight) == 0.08
        assert row.hold_shares == 0  # the ledger is untouched
    finally:
        db.close()


def test_an_unknown_portfolio_is_reported_not_raised(webhook_secret):
    res = _post({"changes": [{"id": "c9", "action": "add", "portfolio_id": "nope", "ts_code": "600866.SH"}]})
    assert res.status_code == 200
    assert res.json()["failed"] == 1
    assert "not found" in res.json()["results"][0]["error"]


def test_unknown_action_is_reported_per_change(webhook_secret, portfolio_id):
    res = _post({"changes": [{"id": "c8", "action": "teleport", "portfolio_id": portfolio_id, "ts_code": "600866.SH"}]})
    assert res.json()["results"][0]["ok"] is False
    assert "action must be" in res.json()["results"][0]["error"]
