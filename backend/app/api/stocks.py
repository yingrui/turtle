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
def search_stocks(q: str = Query(..., min_length=1), _: User = Depends(get_current_user)):
    from app.core.engine.StockRepository import StockRepository

    repo = StockRepository()
    stock = repo.find_stock(q)
    if stock:
        return {"stocks": [{"ts_code": stock.ts_code, "name": stock.name}]}
    return {"stocks": []}


@router.get("")
def list_stocks(
    portfolio: str = Query(...),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    try:
        config = PortfolioService(db).get_portfolio(portfolio)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"stocks": StockService().list_stocks(config)}


@router.get("/{ts_code}/ohlcv")
def stock_ohlcv(ts_code: str, _: User = Depends(get_current_user)):
    return StockService().get_ohlcv(ts_code)


@router.get("/{ts_code}/indicators")
def stock_indicators(ts_code: str, chart: str = Query("ma"), _: User = Depends(get_current_user)):
    try:
        return StockService().get_indicators(ts_code, chart)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{ts_code}/forecast")
def stock_forecast(ts_code: str, body: ForecastRequest, _: User = Depends(get_current_user)):
    return StockService().forecast(ts_code, body.steps)
