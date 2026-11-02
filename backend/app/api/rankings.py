"""Ranking sources: the only thing a simulation may rank by."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.ranking import RankingSource
from app.models.user import User
from app.services.analysis_service import RankingSourceService

router = APIRouter(prefix="/api/rankings", tags=["rankings"], dependencies=[Depends(get_current_user)])


@router.get("")
def list_sources(
    include_deprecated: bool = False,
    include_controls: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return {
        "sources": RankingSourceService().list_sources(db, include_deprecated, include_controls)
    }


@router.get("/{source_id}")
def get_source(source_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    try:
        source = RankingSourceService().get(db, source_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Ranking source not found") from None
    return {
        "id": source.id,
        "kind": source.kind,
        "display_name": source.display_name,
        "description": source.description,
        "method": source.method,
        "params": source.params or {},
        "row_count": source.row_count,
        "date_from": source.date_from,
        "date_to": source.date_to,
        "dataset": {
            "name": source.dataset_name,
            "version": source.dataset_version,
            "manifest_sha256": source.dataset_sha256,
        },
        "label": source.label or {},
        "status": source.status,
        "validation": source.validation or {},
        "artifact_sha256": source.artifact_sha256,
    }


@router.get("/{source_id}/preview")
def preview(
    source_id: str,
    day: date | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    try:
        return {"rows": RankingSourceService().preview(db, source_id, day or date.today(), limit)}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from None
    except KeyError:
        raise HTTPException(status_code=404, detail="Ranking source not found") from None


@router.delete("/{source_id}")
def delete_source(source_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """删掉一个评分模型。被回测引用过的不删 —— 那些回测的结论会失去依据。"""
    from app.models.simulation import SimulationRun

    source = db.get(RankingSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Ranking source not found")
    used = db.query(SimulationRun).filter(SimulationRun.ranking_source_id == source_id).count()
    if used:
        raise HTTPException(
            status_code=409,
            detail=f"已有 {used} 次回测使用过这个模型，不能删除；可以改为停用。",
        )
    db.delete(source)
    db.commit()
    return {"id": source_id, "deleted": True}


@router.post("/{source_id}/deprecate")
def deprecate(source_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    from datetime import datetime

    try:
        source = RankingSourceService().get(db, source_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Ranking source not found") from None
    source.status = "deprecated"
    source.deprecated_at = datetime.utcnow()
    db.commit()
    return {"id": source.id, "status": source.status}
