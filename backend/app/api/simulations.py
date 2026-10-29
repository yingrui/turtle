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


@router.get("/{run_id}/pool")
def simulation_pool(
    run_id: str,
    day: str | None = Query(None, description="Trade date, YYYY-MM-DD (default: the run's last day)"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """The run's stock pool that day — entries it was allowed to hold, held or not.

    `dynamic` runs read the recorded pool; `fixed` runs have one forever (the configured watchlist), so
    it comes from the run's config snapshot instead of thousands of identical rows.
    """
    import json

    from app.core.simulation.model_runner import pool_dates, pool_on

    run = db.get(SimulationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    config = json.loads(run.config_snapshot or "{}")
    if run.pool_mode == "fixed":
        codes = config.get("follow_stocks") or []
        return {
            "run_id": run_id,
            "pool_mode": "fixed",
            "trade_date": day,
            "pool": [{"ts_code": code, "rank": None, "score": None, "held": None} for code in codes],
            "count": len(codes),
        }

    target = date.fromisoformat(day) if day else (pool_dates(db, run_id) or [None])[-1]
    if target is None:
        return {"run_id": run_id, "pool_mode": "dynamic", "trade_date": None, "pool": [], "count": 0}
    rows = pool_on(db, run_id, target)
    return {
        "run_id": run_id,
        "pool_mode": "dynamic",
        "trade_date": target.isoformat(),
        "pool": [
            {
                "ts_code": row.ts_code,
                "rank": row.rank,
                "score": None if row.score is None else float(row.score),
                "held": row.held,
            }
            for row in rows
        ],
        "count": len(rows),
    }


@router.get("/{run_id}/pool-dates")
def simulation_pool_dates(run_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Days the run recorded a pool for (dynamic runs only; a fixed pool has no dates)."""
    from app.core.simulation.model_runner import pool_dates

    run = db.get(SimulationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.pool_mode == "fixed":
        return {"run_id": run_id, "pool_mode": "fixed", "dates": []}
    return {"run_id": run_id, "pool_mode": "dynamic", "dates": pool_dates(db, run_id)}


@router.get("/{run_id}/benchmark")
def simulation_benchmark(
    run_id: str,
    ts_code: str = Query("000300.SH", description="Index to compare against"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """The run's equity next to an index rebased to the same start — "did this beat the market?".

    Both series are rebased to 100 on the run's first day, so the chart answers the question in one
    look instead of asking the reader to divide two percentages.
    """
    from sqlalchemy import select

    from app.models.simulation import SimulationDaily
    from app.services.index_service import IndexService

    run = db.get(SimulationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    daily = db.scalars(
        select(SimulationDaily)
        .where(SimulationDaily.run_id == run_id)
        .order_by(SimulationDaily.trade_date)
    ).all()
    if not daily:
        raise HTTPException(status_code=404, detail="This run has no daily equity yet")
    dates = [row.trade_date.isoformat() for row in daily]
    first = float(daily[0].total or 0) or 1.0
    equity = [round(float(row.total or 0) / first * 100, 4) for row in daily]
    benchmark = IndexService().benchmark_series(db, ts_code, dates)
    return {
        "run_id": run_id,
        "ts_code": ts_code,
        "dates": dates,
        "equity": equity,
        "benchmark": benchmark,
        "excess_pct": (
            None if benchmark[-1] is None or equity[-1] is None else round(equity[-1] - benchmark[-1], 4)
        ),
    }


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


@router.patch("/{run_id}")
def update_run_label(run_id: str, body: dict, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Name or describe an existing run — how a completed experiment gets identified after the fact."""
    run = db.get(SimulationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if "name" in (body or {}):
        run.name = (body["name"] or "").strip() or None
    if "description" in (body or {}):
        run.description = (body["description"] or "").strip() or None
    if "provenance" in (body or {}) and isinstance(body["provenance"], dict):
        run.provenance = body["provenance"]
    db.commit()
    return {
        "run_id": run.id,
        "name": run.name,
        "description": run.description,
        "provenance": run.provenance or {},
    }
