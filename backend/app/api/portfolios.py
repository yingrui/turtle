from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.portfolio_service import PortfolioService

router = APIRouter(prefix="/api/portfolios", tags=["portfolios"], dependencies=[Depends(get_current_user)])


class PortfolioBody(BaseModel):
    config: dict


class CreatePortfolioBody(BaseModel):
    name: str
    config: dict | None = None


class PortfolioYamlBody(BaseModel):
    yaml: str


class WatchlistBody(BaseModel):
    ts_code: str


@router.get("")
def list_portfolios(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    svc = PortfolioService(db)
    return {"portfolios": svc.list_portfolios()}


@router.post("")
def create_portfolio(
    body: CreatePortfolioBody,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    svc = PortfolioService(db)
    try:
        return svc.create_portfolio(body.name, body.config)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{name}/watchlist")
def add_to_watchlist(
    name: str,
    body: WatchlistBody,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    svc = PortfolioService(db)
    try:
        return svc.add_to_watchlist(name, body.ts_code)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{name}")
def get_portfolio(name: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    svc = PortfolioService(db)
    try:
        return svc.get_portfolio(name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{name}/yaml")
def get_portfolio_yaml(name: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    svc = PortfolioService(db)
    try:
        return {"name": name, "yaml": svc.get_portfolio_yaml(name)}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{name}")
def save_portfolio(
    name: str,
    body: PortfolioBody,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    svc = PortfolioService(db)
    try:
        return svc.save_portfolio(name, body.config)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{name}/yaml")
def save_portfolio_yaml(
    name: str,
    body: PortfolioYamlBody,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    svc = PortfolioService(db)
    try:
        return svc.save_portfolio_yaml(name, body.yaml)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{name}")
def delete_portfolio(name: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    svc = PortfolioService(db)
    try:
        svc.delete_portfolio(name)
        return {"ok": True}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
