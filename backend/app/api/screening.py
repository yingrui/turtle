from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.auth import get_current_user
from app.models.user import User
from app.services.screening_service import ScreeningService

router = APIRouter(prefix="/api/screening", tags=["screening"], dependencies=[Depends(get_current_user)])


class ScreenRequest(BaseModel):
    as_of_date: str
    ignore_st: bool = True
    ma_window_1: int = 20
    ma_window_2: int = 70
    ma_window_3: int = 150
    trend_filter: str | None = None


@router.post("")
def run_screen(body: ScreenRequest, _: User = Depends(get_current_user)):
    """Run universe screening (trend + ADF). Long-running on full market — prefer job API for production."""
    rows = ScreeningService().run_screen(
        date.fromisoformat(body.as_of_date),
        ignore_st=body.ignore_st,
        ma_window_1=body.ma_window_1,
        ma_window_2=body.ma_window_2,
        ma_window_3=body.ma_window_3,
        trend_filter=body.trend_filter,
    )
    return {"count": len(rows), "stocks": rows[:500]}
