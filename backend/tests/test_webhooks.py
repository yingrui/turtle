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


# --- nothing is indexed automatically --------------------------------------
def test_a_change_that_was_applied_does_not_index_anything(webhook_secret, portfolio_id, monkeypatch):
    """Re-indexing is an explicit call: the graph is refreshed when someone asks for it."""
    import app.api.webhooks as webhooks_module

    assert not hasattr(webhooks_module, "openkms_sync")
    res = _post({"changes": [{"id": "c1", "action": "add", "portfolio_id": portfolio_id, "ts_code": "600519.SH"}]})
    assert res.json()["applied"] == 1


# --- the generic Action envelope -------------------------------------------
def _action_envelope(**overrides):
    body = {
        "event": "action.executed",
        "action": {"api_name": "setHoldingWeight", "rule_type": "object_modify"},
        "object": {
            "object_type": "Holding",
            "id": "h-1",
            "properties": {"portfolio_id": None, "ts_code": "600519.SH", "target_weight": 0.01},
        },
        "input": {"target_weight": 0.05},
        "applied": {"modified_ids": ["h-1"]},
    }
    body.update(overrides)
    return body


def test_an_action_envelope_mirrors_the_holding(webhook_secret, portfolio_id):
    envelope = _action_envelope()
    envelope["object"]["properties"]["portfolio_id"] = portfolio_id
    res = _post(envelope)
    assert res.status_code == 200, res.text
    assert res.json()["applied"] == 1

    db = SessionLocal()
    try:
        row = (
            db.query(PortfolioStock)
            .filter(PortfolioStock.portfolio_id == portfolio_id, PortfolioStock.ts_code == "600519.SH")
            .one()
        )
        assert float(row.target_weight) == 0.05
        assert row.hold_shares == 0
    finally:
        db.close()


def test_only_the_fields_the_action_touched_are_written(webhook_secret, portfolio_id):
    envelope = _action_envelope()
    envelope["object"]["properties"].update(
        {"portfolio_id": portfolio_id, "ts_code": "600036.SH", "status": "holding", "note": "object"}
    )
    envelope["input"] = {"target_weight": 0.02}
    assert _post(envelope).json()["applied"] == 1
    db = SessionLocal()
    try:
        row = (
            db.query(PortfolioStock)
            .filter(PortfolioStock.portfolio_id == portfolio_id, PortfolioStock.ts_code == "600036.SH")
            .one()
        )
        assert float(row.target_weight) == 0.02
        assert row.status == "watching"  # not copied from the mirror
        assert row.note == ""
    finally:
        db.close()


def test_an_action_envelope_for_another_object_type_is_refused(webhook_secret, portfolio_id):
    envelope = _action_envelope()
    envelope["object"] = {"object_type": "Stock", "id": "x", "properties": {"ts_code": "1"}}
    assert _post(envelope).status_code == 400
