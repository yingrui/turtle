"""Factor library API: the catalogue, a factor's values, and running it.

Reads are cheap (indexed by the factor's natural key). Computation is an explicit request that
becomes a job, because it walks the whole market panel for the window.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import FactorValue
from app.models.user import User
from app.services.factor_service import FactorError, FactorService
from app.services.job_service import JobService

router = APIRouter(prefix="/api/factors", tags=["factors"], dependencies=[Depends(get_current_user)])


def _definition_dict(definition) -> dict:
    return {
        "code": definition.code,
        "name": definition.name,
        "category": definition.category,
        "direction": definition.direction,
        "unit": definition.unit,
        "logic": definition.logic,
        "formula": definition.formula,
        "params": definition.params or {},
        "lookback_days": definition.lookback_days,
        "ic_ir": None if definition.ic_ir is None else float(definition.ic_ir),
        "source_ref": definition.source_ref,
        "is_computable": bool(definition.formula),
    }


@router.get("")
def list_factors(
    computable: bool | None = Query(None, description="Only factors the engine can compute"),
    category: str | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    factors = FactorService().list_definitions(db)
    if computable is not None:
        factors = [f for f in factors if f["is_computable"] == computable]
    if category:
        factors = [f for f in factors if f["category"] == category]
    return {
        "factors": factors,
        "total": len(factors),
        "computable": sum(1 for f in factors if f["is_computable"]),
        "categories": sorted({f["category"] for f in factors}),
    }


@router.get("/{code}")
def get_factor(code: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    try:
        service = FactorService()
        definition = service.get_definition(db, code)
    except FactorError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    payload = _definition_dict(definition)
    latest = db.execute(
        select(
            func.count().label("rows"),
            func.max(FactorValue.trade_date).label("last_date"),
            func.min(FactorValue.trade_date).label("first_date"),
            func.count(func.distinct(FactorValue.ts_code)).label("stocks"),
        ).where(FactorValue.factor_id == definition.id)
    ).one()
    payload.update(
        {
            "value_count": int(latest.rows or 0),
            "stock_count": int(latest.stocks or 0),
            "first_date": latest.first_date,
            "last_date": latest.last_date,
        }
    )
    return payload


@router.get("/{code}/dates")
def list_factor_dates(
    code: str,
    limit: int = Query(60, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Dates that have values, newest first — what a cross-section picker offers."""
    try:
        definition = FactorService().get_definition(db, code)
    except FactorError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    dates = db.scalars(
        select(FactorValue.trade_date)
        .where(FactorValue.factor_id == definition.id)
        .group_by(FactorValue.trade_date)
        .order_by(FactorValue.trade_date.desc())
        .limit(limit)
    ).all()
    return {"code": code, "dates": dates}


@router.get("/{code}/values")
def get_factor_values(
    code: str,
    ts_code: str | None = Query(None, description="One stock's history"),
    trade_date: date | None = Query(None, description="One day across every stock"),
    start: date | None = Query(None),
    end: date | None = Query(None),
    sort: str = Query("value", pattern="^(value|ts_code|trade_date)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    try:
        definition = FactorService().get_definition(db, code)
    except FactorError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    query = select(FactorValue).where(FactorValue.factor_id == definition.id)
    if ts_code:
        query = query.where(FactorValue.ts_code == ts_code)
    if trade_date:
        query = query.where(FactorValue.trade_date == trade_date)
    if start:
        query = query.where(FactorValue.trade_date >= start)
    if end:
        query = query.where(FactorValue.trade_date <= end)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    column = getattr(FactorValue, sort)
    query = query.order_by(column.desc() if order == "desc" else column.asc())
    rows = db.scalars(query.limit(limit).offset(offset)).all()
    return {
        "code": definition.code,
        "name": definition.name,
        "direction": definition.direction,
        "unit": definition.unit,
        "total": int(total),
        "rows": [
            {
                "ts_code": row.ts_code,
                "trade_date": row.trade_date,
                "value": float(row.value),
                "extra": row.extra,
            }
            for row in rows
        ],
    }


@router.post("/{code}/compute")
def compute_factor(
    code: str,
    start: date | None = Query(None),
    end: date | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Start a computation job — the market panel is too large to hold a request open."""
    try:
        definition = FactorService().get_definition(db, code)
    except FactorError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not definition.formula:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{code} is a definition only: its inputs are not in this database, so there is "
                "nothing to compute yet"
            ),
        )
    payload = {"code": definition.code}
    if start:
        payload["start"] = start.isoformat()
    if end:
        payload["end"] = end.isoformat()
    job = JobService().create_job(db, "factor_compute", payload)
    return {"job_id": job.id, "code": definition.code, "status": job.status}
