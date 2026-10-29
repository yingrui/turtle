"""Index quotes and benchmarks."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.index_service import IndexService

router = APIRouter(prefix="/api/indexes", tags=["indexes"], dependencies=[Depends(get_current_user)])


@router.get("")
def list_indexes(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Every index that has daily bars, the broad benchmarks first."""
    return {"indexes": IndexService().list_indexes(db)}


@router.get("/{ts_code}/daily")
def index_daily(
    ts_code: str,
    start: date | None = Query(None),
    end: date | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    end = end or date.today()
    start = start or date(end.year - 1, end.month, end.day)
    data = IndexService().daily(db, ts_code, start, end)
    if not data["dates"]:
        raise HTTPException(status_code=404, detail=f"no index data for {ts_code} in that window")
    return data
