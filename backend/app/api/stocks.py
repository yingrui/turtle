from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.portfolio_service import PortfolioService
from app.services.stock_service import StockService

router = APIRouter(prefix="/api/stocks", tags=["stocks"], dependencies=[Depends(get_current_user)])


class ForecastRequest(BaseModel):
    steps: int = 10


@router.get("/search")
def search_stocks(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=50),
    _: User = Depends(get_current_user),
):
    return {"stocks": StockService().search_stocks(q, limit=limit)}


@router.get("/universe/meta")
def universe_meta(_: User = Depends(get_current_user)):
    return StockService().get_universe_meta()


@router.get("/universe/industry-summary")
def industry_summary(
    list_status: str = Query("L"),
    exclude_st: bool = Query(True),
    limit: int = Query(30, ge=1, le=100),
    _: User = Depends(get_current_user),
):
    return StockService().get_industry_summary(
        list_status=list_status,
        exclude_st=exclude_st,
        limit=limit,
    )


@router.get("/universe")
def list_universe(
    q: str | None = None,
    exchange: str | None = None,
    market: str | None = None,
    industry: str | None = None,
    list_status: str = Query("L"),
    exclude_st: bool = Query(True),
    page: int = Query(0, ge=0),
    page_size: int = Query(50, ge=1, le=100),
    sort: str = Query("ts_code"),
    order: str = Query("asc"),
    _: User = Depends(get_current_user),
):
    return StockService().list_universe(
        q=q,
        exchange=exchange,
        market=market,
        industry=industry,
        list_status=list_status,
        exclude_st=exclude_st,
        page=page,
        page_size=page_size,
        sort=sort,
        order=order,
    )


@router.get("")
def list_portfolio_stocks(
    portfolio: str = Query(...),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    try:
        config = PortfolioService(db).get_portfolio(portfolio)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"stocks": StockService().list_stocks(config)}


@router.get("/{ts_code}/snapshot")
def stock_snapshot(ts_code: str, _: User = Depends(get_current_user)):
    snap = StockService().get_stock_snapshot(ts_code)
    if snap is None:
        raise HTTPException(status_code=404, detail=f"Stock not found: {ts_code}")
    return snap


@router.get("/{ts_code}/ohlcv")
def stock_ohlcv(
    ts_code: str,
    limit: int = Query(250, ge=0, le=2000),
    _: User = Depends(get_current_user),
):
    return StockService().get_ohlcv(ts_code, limit=limit)


@router.get("/{ts_code}/indicators")
def stock_indicators(ts_code: str, chart: str = Query("ma"), _: User = Depends(get_current_user)):
    try:
        return StockService().get_indicators(ts_code, chart)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{ts_code}/forecast")
def stock_forecast(ts_code: str, body: ForecastRequest, _: User = Depends(get_current_user)):
    return StockService().forecast(ts_code, body.steps)
