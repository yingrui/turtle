from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth import get_current_user
from app.models.user import User
from app.services.stock_pick_service import StockPickService

router = APIRouter(prefix="/api/stock-pick", tags=["stock-pick"], dependencies=[Depends(get_current_user)])


class StockPickRequest(BaseModel):
    as_of_date: date | None = None
    q: str | None = None
    industry: str | None = None
    list_status: str = "L"
    exclude_st: bool = True
    exclude_limit: bool = True
    pe_ttm_min: float | None = None
    pe_ttm_max: float | None = None
    pb_min: float | None = None
    pb_max: float | None = None
    ps_ttm_min: float | None = None
    ps_ttm_max: float | None = None
    circ_mv_min: float | None = None
    circ_mv_max: float | None = None
    total_mv_min: float | None = None
    total_mv_max: float | None = None
    turnover_rate_min: float | None = None
    turnover_rate_max: float | None = None
    sort: str = "circ_mv"
    order: str = "asc"
    limit: int = Field(200, ge=1, le=500)


@router.get("/presets")
def list_presets(_: User = Depends(get_current_user)):
    return {"presets": StockPickService().get_presets()}


@router.post("")
def run_stock_pick(body: StockPickRequest, _: User = Depends(get_current_user)):
    return StockPickService().pick_stocks(**body.model_dump())
