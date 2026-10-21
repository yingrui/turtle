"""Inbound webhooks from openKMS — the ontology proposes, this app applies.

A Function in openKMS cannot write this database (it may only reach the HTTP surface), so a
portfolio change travels as a *proposal*: the agent creates `PortfolioChange` objects in the
ontology, then a Function posts them here. This endpoint is the only door, it is signed with a
shared secret, and it applies changes through `PortfolioService` so ledger invariants hold —
`hold_shares` / `avg_cost` stay aggregates of `portfolio_transactions`, never a raw write.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.portfolio import Portfolio
from app.services.portfolio_service import STATUSES, PortfolioService

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

SIGNATURE_HEADER = "X-OpenKMS-Signature"
SUPPORTED_ACTIONS = ("add", "remove", "set_weight", "set_status")


def _expected_signature(raw_body: bytes) -> str:
    secret = settings.stock_openkms_webhook_secret.encode("utf-8")
    return "sha256=" + hmac.new(secret, raw_body, hashlib.sha256).hexdigest()


def _verify_signature(raw_body: bytes, header: str | None) -> None:
    if not settings.stock_openkms_webhook_secret:
        # Fail closed: an unset secret must not turn this into an open write endpoint.
        raise HTTPException(status_code=503, detail="openKMS webhooks are not configured")
    if not header or not hmac.compare_digest(_expected_signature(raw_body), header.strip()):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")


def _portfolio_name(db: Session, portfolio_id: str | None) -> str:
    if not portfolio_id:
        raise ValueError("portfolio_id is required")
    portfolio = db.get(Portfolio, portfolio_id)
    if portfolio is None:
        raise ValueError(f"portfolio {portfolio_id} not found")
    return portfolio.name


def _apply_change(svc: PortfolioService, change: dict[str, Any]) -> dict[str, Any]:
    change_id = str(change.get("id") or "")
    action = str(change.get("action") or "")
    ts_code = str(change.get("ts_code") or "").strip().upper()
    try:
        if action not in SUPPORTED_ACTIONS:
            raise ValueError(f"action must be one of {', '.join(SUPPORTED_ACTIONS)}")
        name = _portfolio_name(svc.db, change.get("portfolio_id"))
        if not ts_code:
            raise ValueError("ts_code is required")
        if action in ("add", "remove"):
            if action == "add":
                svc.upsert_stock(name, ts_code, {"status": "watching"})
            else:
                # A position with holdings or history is closed, not deleted — the ledger stays.
                try:
                    svc.remove_stock(name, ts_code)
                except ValueError:
                    svc.upsert_stock(name, ts_code, {"status": "closed"})
        elif action == "set_weight":
            weight = change.get("target_weight")
            if weight is None:
                raise ValueError("target_weight is required for set_weight")
            svc.upsert_stock(name, ts_code, {"target_weight": weight})
        else:  # set_status
            target = str(change.get("target_status") or "")
            if target not in STATUSES:
                raise ValueError(f"target_status must be one of {', '.join(STATUSES)}")
            svc.upsert_stock(name, ts_code, {"status": target})
        return {"id": change_id, "ok": True}
    except (ValueError, FileNotFoundError) as exc:
        return {"id": change_id, "ok": False, "error": str(exc)}


@router.post("/openkms/portfolio-changes")
async def openkms_portfolio_changes(request: Request, db: Session = Depends(get_db)):
    """Apply proposed holding changes. Idempotent per change: applying twice is a no-op."""
    raw = await request.body()
    _verify_signature(raw, request.headers.get(SIGNATURE_HEADER))
    try:
        payload = json.loads(raw or b"{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Body must be JSON") from exc
    changes = payload.get("changes")
    if not isinstance(changes, list) or not changes:
        raise HTTPException(status_code=400, detail="changes[] is required")

    svc = PortfolioService(db)
    results = [_apply_change(svc, change if isinstance(change, dict) else {}) for change in changes]
    return {
        "applied": sum(1 for r in results if r["ok"]),
        "failed": sum(1 for r in results if not r["ok"]),
        "results": results,
    }
