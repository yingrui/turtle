from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.portfolio_lifecycle_service import events_on, members_on
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


class WatchlistBulkBody(BaseModel):
    ts_codes: list[str]


class StockBody(BaseModel):
    ts_code: str
    #: Optional caller-supplied identity: the ontology creates the Holding object first and the
    #: row must carry the same id, or the next index sees two objects for one holding.
    id: str | None = None
    status: str | None = None
    target_amount: float | None = None
    target_weight: float | None = None
    stop_loss_point: float | None = None
    max_holding_days: int | None = None
    atr: float | None = None
    note: str | None = None


class StockPatchBody(BaseModel):
    status: str | None = None
    target_amount: float | None = None
    target_weight: float | None = None
    stop_loss_point: float | None = None
    max_holding_days: int | None = None
    atr: float | None = None
    note: str | None = None


class TransactionBody(BaseModel):
    ts_code: str
    side: str
    shares: int
    price: float
    trade_date: str | None = None
    amount: float | None = None
    fee: float | None = None
    tax: float | None = None
    stop_loss_point: float | None = None
    reason: str | None = None
    source: str | None = None


class RiskControlBody(BaseModel):
    risk_control: dict


class PoliciesBody(BaseModel):
    policies: list[dict]


class CashFlowBody(BaseModel):
    flow_date: str
    amount: float
    kind: str | None = None
    note: str | None = None


@router.get("")
def list_portfolios(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    svc = PortfolioService(db)
    return {"portfolios": svc.list_portfolios()}


@router.get("/watchlist")
def list_watchlist(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    svc = PortfolioService(db)
    return svc.list_watchlist_with_quotes()


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


@router.post("/{name}/watchlist/bulk")
def bulk_add_to_watchlist(
    name: str,
    body: WatchlistBulkBody,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    svc = PortfolioService(db)
    try:
        return svc.add_many_to_watchlist(name, body.ts_codes)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{name}/watchlist/{ts_code}")
def remove_from_watchlist(
    name: str,
    ts_code: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    svc = PortfolioService(db)
    try:
        return svc.remove_from_watchlist(name, ts_code)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{name}/watchlist")
def get_portfolio_watchlist(
    name: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    svc = PortfolioService(db)
    try:
        return svc.list_portfolio_watchlist_with_quotes(name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{name}/members")
def portfolio_members(
    name: str,
    day: str = Query(..., description="Trade date, YYYY-MM-DD — the portfolio's membership that day"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Which stocks were in the portfolio that day (a range query over membership intervals)."""
    portfolio_id = PortfolioService(db).get_portfolio_id(name)
    rows = members_on(db, portfolio_id, date.fromisoformat(day))
    return {
        "portfolio": name,
        "trade_date": day,
        "members": [
            {
                "ts_code": row.ts_code,
                "status": row.status,
                "episode": row.episode,
                "joined_at": row.joined_at,
                "left_at": row.left_at,
            }
            for row in rows
        ],
    }


@router.get("/{name}/events")
def portfolio_events(
    name: str,
    day: str | None = Query(None, description="Only this trade date"),
    limit: int = Query(200, ge=1, le=2000),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """The daily decisions: what changed, why, at what rank, under which model."""
    portfolio_id = PortfolioService(db).get_portfolio_id(name)
    rows = events_on(db, portfolio_id, date.fromisoformat(day) if day else None, limit=limit)
    return {
        "portfolio": name,
        "events": [
            {
                "trade_date": row.trade_date,
                "ts_code": row.ts_code,
                "event": row.event,
                "from_status": row.from_status,
                "to_status": row.to_status,
                "episode": row.episode,
                "score": None if row.score is None else float(row.score),
                "rank": row.rank,
                "reason": row.reason,
                "rule": row.rule,
                "rule_params": row.rule_params,
                "model_name": row.model_name,
                "model_version": row.model_version,
                "dataset_version": row.dataset_version,
                "source": row.source,
            }
            for row in rows
        ],
    }


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


# --------------------------------------------------------------- stocks

@router.get("/{name}/stocks")
def list_portfolio_stocks(
    name: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    svc = PortfolioService(db)
    try:
        return {"stocks": svc.list_stocks(name)}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{name}/stocks")
def upsert_portfolio_stock(
    name: str,
    body: StockBody,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    svc = PortfolioService(db)
    try:
        return svc.upsert_stock(name, body.ts_code, body.model_dump(exclude={"ts_code"}))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/{name}/stocks/{ts_code}")
def patch_portfolio_stock(
    name: str,
    ts_code: str,
    body: StockPatchBody,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    svc = PortfolioService(db)
    try:
        return svc.upsert_stock(name, ts_code, body.model_dump(exclude_none=True))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{name}/stocks/{ts_code}")
def delete_portfolio_stock(
    name: str,
    ts_code: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    svc = PortfolioService(db)
    try:
        svc.remove_stock(name, ts_code)
        return {"ok": True}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{name}/stocks/{ts_code}/rebuild")
def rebuild_portfolio_stock(
    name: str,
    ts_code: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    svc = PortfolioService(db)
    try:
        return svc.rebuild_stock_from_transactions(name, ts_code)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# --------------------------------------------------------------- transactions

@router.get("/{name}/equity")
def portfolio_equity(
    name: str,
    days: int = Query(180, ge=5, le=2000),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    svc = PortfolioService(db)
    try:
        return svc.equity_curve(name, days=days)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{name}/transactions")
def list_portfolio_transactions(
    name: str,
    ts_code: str | None = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    svc = PortfolioService(db)
    try:
        return {
            "transactions": svc.list_transactions(
                name, ts_code=ts_code, limit=limit, offset=offset
            )
        }
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{name}/transactions")
def create_portfolio_transaction(
    name: str,
    body: TransactionBody,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    svc = PortfolioService(db)
    try:
        return svc.record_transaction(name, body.model_dump())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# --------------------------------------------------------------- risk / policies / cash

@router.get("/{name}/risk-control")
def get_risk_control(name: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    svc = PortfolioService(db)
    try:
        return svc.get_risk_control(name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{name}/risk-control")
def update_risk_control(
    name: str,
    body: RiskControlBody,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    svc = PortfolioService(db)
    try:
        return svc.update_risk_control(name, body.risk_control)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{name}/policies")
def list_policies(name: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    svc = PortfolioService(db)
    try:
        return {"policies": svc.list_policies(name)}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{name}/policies")
def replace_policies(
    name: str,
    body: PoliciesBody,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    svc = PortfolioService(db)
    try:
        return {"policies": svc.replace_policies(name, body.policies)}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{name}/cash-flows")
def list_cash_flows(name: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    svc = PortfolioService(db)
    try:
        return {"cash_flows": svc.list_cash_flows(name)}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{name}/cash-flows")
def create_cash_flow(
    name: str,
    body: CashFlowBody,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    svc = PortfolioService(db)
    try:
        return svc.create_cash_flow(name, body.model_dump())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
