"""Model artifacts: what has been trained, for which period, and whether a run would reuse it."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.model_artifact import ModelArtifact
from app.models.user import User

router = APIRouter(prefix="/api/models", tags=["models"], dependencies=[Depends(get_current_user)])


@router.get("")
def list_models(
    period: str | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = db.query(ModelArtifact)
    if period:
        query = query.filter(ModelArtifact.period == period)
    rows = query.order_by(ModelArtifact.period.desc()).limit(limit).all()
    return {
        "models": [
            {
                "fingerprint": row.fingerprint,
                "period": row.period,
                "period_kind": row.period_kind,
                "method": row.method,
                "params": row.params or {},
                "label": row.label or {},
                "dataset": {
                    "name": row.dataset_name,
                    "version": row.dataset_version,
                    "manifest_sha256": row.dataset_sha256,
                },
                "metrics": row.metrics or {},
                "status": row.status,
                "artifact_sha256": row.artifact_sha256,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]
    }


@router.get("/{fingerprint}")
def get_model(fingerprint: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    row = db.get(ModelArtifact, fingerprint)
    if not row:
        raise HTTPException(status_code=404, detail="Model not found")
    return {
        "fingerprint": row.fingerprint,
        "period": row.period,
        "period_kind": row.period_kind,
        "method": row.method,
        "params": row.params or {},
        "label": row.label or {},
        "metrics": row.metrics or {},
        "artifact_key": row.artifact_key,
        "artifact_sha256": row.artifact_sha256,
    }
