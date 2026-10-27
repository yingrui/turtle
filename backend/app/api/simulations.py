from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.user import User
from app.models.simulation import SimulationRun
from app.services.simulation_service import SimulationService

router = APIRouter(prefix="/api/simulations", tags=["simulations"], dependencies=[Depends(get_current_user)])


@router.get("")
def list_simulations(
    job_id: str | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return {"runs": SimulationService().list_runs(db, job_id=job_id)}


@router.get("/compare")
def compare_simulations(
    job_id: str = Query(...),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return {"policies": SimulationService().compare_job_runs(db, job_id)}


@router.get("/{run_id}/summary")
def simulation_summary(run_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    try:
        return SimulationService().get_summary(db, run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{run_id}/holdings")
def simulation_holdings(
    run_id: str,
    day: str = Query(..., description="Trade date, YYYY-MM-DD"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """What the run held at that day's close — the run's own book, not the live portfolio."""
    from app.core.simulation.model_runner import holdings_on

    run = db.get(SimulationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    rows = holdings_on(db, run_id, date.fromisoformat(day))
    return {
        "run_id": run_id,
        "trade_date": day,
        "mode": run.mode,
        "holdings": [
            {
                "ts_code": row.ts_code,
                "shares": row.shares,
                "price": float(row.price),
                "market_value": float(row.market_value),
                "weight": None if row.weight is None else float(row.weight),
                "rank": row.rank,
                "score": None if row.score is None else float(row.score),
            }
            for row in rows
        ],
        "count": len(rows),
    }


@router.get("/{run_id}/holding-dates")
def simulation_holding_dates(run_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """The dates this run recorded a book for, oldest first."""
    from app.core.simulation.model_runner import holding_dates

    if not db.get(SimulationRun, run_id):
        raise HTTPException(status_code=404, detail="Run not found")
    return {"run_id": run_id, "dates": holding_dates(db, run_id)}


@router.get("/{run_id}/daily")
def simulation_daily_chart(run_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return SimulationService().get_daily_chart(db, run_id)


@router.get("/{run_id}/trades")
def simulation_trades(run_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return {"trades": SimulationService().get_trades(db, run_id)}


@router.get("/{run_id}/benefit")
def simulation_benefit(run_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return {"benefit": SimulationService().get_benefit_by_stock(db, run_id)}


@router.get("/{run_id}/win-loss")
def simulation_win_loss(run_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return SimulationService().get_win_loss(db, run_id)
