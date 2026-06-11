from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.user import User
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
