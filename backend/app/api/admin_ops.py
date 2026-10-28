"""Operator endpoints: read the database connection budget, release what this app holds.

Small on purpose — this is a maintenance surface, not a console. The destructive action is bounded by
`db_admin_service`: only this app's pools, only idle backends, only after a grace period.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.database import get_db
from app.models.user import User
from app.services import db_admin_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/db-connections")
def db_connections(
    min_idle_seconds: int = Query(db_admin_service.DEFAULT_MIN_IDLE_SECONDS, ge=0, le=86400),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Who holds connections right now, and how many of them this app may release."""
    return db_admin_service.report(db, min_idle_seconds=min_idle_seconds)


@router.post("/db-connections/release")
def release_db_connections(
    min_idle_seconds: int = Query(db_admin_service.DEFAULT_MIN_IDLE_SECONDS, ge=0, le=86400),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Release this app's idle connections. `min_idle_seconds=0` is allowed but rarely what you want."""
    return db_admin_service.release_idle(db, min_idle_seconds=min_idle_seconds)
