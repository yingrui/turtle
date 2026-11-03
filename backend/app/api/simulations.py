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


def _excess_of(db, run_id: str, ts_code: str) -> float | None:
    """Same rebasing as `/benchmark`, shared so the comparison and the chart never disagree."""
    from sqlalchemy import select

    from app.models.simulation import SimulationDaily
    from app.services.index_service import IndexService

    daily = db.scalars(
        select(SimulationDaily)
        .where(SimulationDaily.run_id == run_id)
        .order_by(SimulationDaily.trade_date)
    ).all()
    if not daily:
        return None
    dates = [row.trade_date.isoformat() for row in daily]
    first = float(daily[0].total or 0) or 1.0
    equity_last = float(daily[-1].total or 0) / first * 100
    benchmark = IndexService().benchmark_series(db, ts_code, dates)
    if not benchmark or benchmark[-1] is None:
        return None
    return round(equity_last - benchmark[-1], 4)


@router.post("/{run_id}/baselines")
def launch_baselines(
    run_id: str,
    count: int = Query(3, ge=1, le=10),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Run the same window with stocks picked at random — the number that turns a return into a verdict.

    The baselines use the run's own strategy, window and portfolio, and differ only in where the pool
    comes from. Anything else would compare two different experiments.
    """
    import json as _json
    import uuid

    from app.models.job import Job
    from app.models.ranking import RankingSource
    from app.services.analysis_service import run_analysis

    run = db.get(SimulationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if not run.ranking_source_id:
        raise HTTPException(status_code=422, detail="This run has no ranking source to randomise")
    source = db.get(RankingSource, run.ranking_source_id)
    # A finished run records its window; an older one only has the equity rows, so read those.
    from sqlalchemy import func, select

    from app.models.simulation import SimulationDaily

    start = run.window_start
    end = run.window_end
    if not start or not end:
        first, last = db.execute(
            select(func.min(SimulationDaily.trade_date), func.max(SimulationDaily.trade_date))
            .where(SimulationDaily.run_id == run_id)
        ).one()
        start = start or first
        end = end or last
    if not start or not end:
        raise HTTPException(status_code=422, detail="This run has no window to repeat")

    created = []
    for index in range(count):
        source_id = f"{run_id[:8]}-random-{index + 1}"
        # A real random basket, produced by the same analysis machinery as any other source — not a
        # pointer to the original artifact, which would make every baseline identical to the run.
        run_analysis(
            db,
            method="constant_pool",
            params={"size": 50, "seed": 1000 + index, "start": start, "end": end},
            source_id=source_id,
            display_name=f"随机对照 {index + 1}（{start}…{end}）",
        )
        payload = {
            "type": "simulation",
            "mode": "model",
            "buy_rule": "pool_entry",
            "portfolio": run.portfolio_name,
            "ranking_source_id": source_id,
            "start_date": str(start),
            "end_date": str(end),
            "retrain": "none",
            "name": f"{run.name or run.id[:8]} · 随机对照 {index + 1}",
            "description": f"主结果 {run.id} 的对照",
        }
        # Jobs run as threads owned by the service; inserting a row directly would leave it pending
        # forever, because nothing polls the table.
        from app.services.job_service import JobService

        job = JobService().create_job(db, "simulation", payload)
        created.append({"source_id": source_id, "job_id": job.id})

    provenance = dict(run.provenance or {})
    # A launch replaces the previous set: measuring against two generations of baselines would mix
    # different windows' luck into one spread.
    provenance["baselines"] = [item["job_id"] for item in created]
    run.provenance = provenance
    db.commit()
    return {"run_id": run_id, "created": created}


@router.get("/{run_id}/comparison")
def simulation_comparison(
    run_id: str,
    ts_code: str = Query("000300.SH"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """How this run's excess compares with the runs that picked stocks at random.

    The question a single number cannot answer: is +9 points skill, or is it what any basket did this
    year? The answer is a multiple of the spread between those random baskets.
    """
    run = db.get(SimulationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    provenance = run.provenance or {}
    # `baselines` holds job ids: a run row only exists once the job has started.
    baseline_jobs = provenance.get("baselines") or []
    mine = _excess_of(db, run_id, ts_code)
    rows = []
    for job_id in baseline_jobs:
        baseline = db.query(SimulationRun).filter(SimulationRun.job_id == job_id).first()
        if not baseline:
            rows.append({"run_id": None, "job_id": job_id, "name": None, "excess_pct": None, "finished": False})
            continue
        rows.append(
            {
                "run_id": baseline.id,
                "job_id": job_id,
                "name": baseline.name,
                "excess_pct": _excess_of(db, baseline.id, ts_code),
                "finished": baseline.finished_at is not None,
            }
        )
    values = [row["excess_pct"] for row in rows if row["excess_pct"] is not None]
    spread = None
    sigma = None
    if len(values) >= 2:
        import statistics

        mean = statistics.mean(values)
        sd = statistics.stdev(values)
        spread = {"mean": round(mean, 4), "sd": round(sd, 4), "n": len(values)}
        if sd:
            sigma = None if mine is None else round((mine - mean) / sd, 2)
    return {
        "run_id": run_id,
        "excess_pct": mine,
        "baselines": rows,
        "spread": spread,
        "sigma": sigma,
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
    opened, costs = _holding_context(db, run_id, [row.ts_code for row in rows])
    from app.models.simulation import SimulationDaily

    equity_row = db.query(SimulationDaily).filter(
        SimulationDaily.run_id == run_id, SimulationDaily.trade_date == date.fromisoformat(day)
    ).first()
    when = date.fromisoformat(day)
    return {
        "run_id": run_id,
        "trade_date": day,
        "mode": run.mode,
        "holdings": [
            {
                "ts_code": row.ts_code,
                "shares": row.shares,
                # The run's own close for that day: viewing 2026-03-31 must not show today's price.
                "price": float(row.price),
                "market_value": float(row.market_value),
                "weight": None if row.weight is None else float(row.weight),
                "rank": row.rank,
                "score": None if row.score is None else float(row.score),
                "opened_at": opened.get(row.ts_code).isoformat() if opened.get(row.ts_code) else None,
                "holding_days": (when - opened[row.ts_code]).days if opened.get(row.ts_code) else None,
                "avg_cost": costs.get(row.ts_code),
                "unrealized_pnl": (
                    None if costs.get(row.ts_code) is None
                    else round((float(row.price) - costs[row.ts_code]) * row.shares, 2)
                ),
                "unrealized_pct": (
                    None if not costs.get(row.ts_code)
                    else round((float(row.price) / costs[row.ts_code] - 1) * 100, 2)
                ),
            }
            for row in rows
        ],
        "count": len(rows),
        # Cash belongs next to the positions: value + cash − initial capital is the account's result,
        # and without it the number cannot be checked.
        "cash": None if equity_row is None or equity_row.balance is None else float(equity_row.balance),
        "total": None if equity_row is None or equity_row.total is None else float(equity_row.total),
    }


def _holding_context(db, run_id: str, codes: list[str]) -> tuple[dict, dict]:
    """When each name was bought and at what average cost, from the run's own fills.

    Both answers live in the trade log: the first buy is the opening date, and buys up to now give the
    average cost. Storing them on every daily row would be the same numbers repeated 300 times.
    """
    from app.models.simulation import SimulationTrade

    opened: dict = {}
    average: dict = {}
    shares: dict = {}
    trades = (
        db.query(SimulationTrade)
        .filter(SimulationTrade.run_id == run_id, SimulationTrade.ts_code.in_(codes))
        .order_by(SimulationTrade.trade_date)
        .all()
    )
    for trade in trades:
        code = trade.ts_code
        if trade.side == "buy":
            qty = float(trade.shares)
            total = average.get(code, 0.0) * shares.get(code, 0.0) + float(trade.amount) + float(trade.fee or 0)
            shares[code] = shares.get(code, 0.0) + qty
            average[code] = total / shares[code] if shares[code] else None
            opened.setdefault(code, trade.trade_date)
        else:
            shares[code] = max(0.0, shares.get(code, 0.0) - float(trade.shares))
            if shares[code] == 0:
                average.pop(code, None)
                opened.pop(code, None)
    return opened, average


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
    if "verdict" in (body or {}) and isinstance(body["verdict"], dict):
        run.verdict = body["verdict"]
    db.commit()
    return {
        "run_id": run.id,
        "name": run.name,
        "description": run.description,
        "provenance": run.provenance or {},
        "verdict": run.verdict or {},
    }


@router.delete("/{run_id}")
def delete_run(run_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Delete a run and everything it owns.

    A run's trades, holdings, pool and daily curve only exist for that run, so they go with it. A
    portfolio pointing at it through `active_run_id` is detached rather than deleted — the portfolio
    is the long-lived thing.
    """
    from app.models.portfolio import Portfolio
    from app.models.simulation import SimulationDaily, SimulationHolding, SimulationPool, SimulationTrade

    run = db.get(SimulationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.job_id:
        from app.models.run import Run

        job = db.get(Run, run.job_id)
        if job and job.status in {"pending", "running"}:
            raise HTTPException(status_code=409, detail="The job that owns this run is still running")
    removed = {}
    for model in (SimulationTrade, SimulationHolding, SimulationPool, SimulationDaily):
        removed[model.__tablename__] = (
            db.query(model).filter(model.run_id == run_id).delete(synchronize_session=False)
        )
    db.query(Portfolio).filter(Portfolio.active_run_id == run_id).update(
        {Portfolio.active_run_id: None}, synchronize_session=False
    )
    db.delete(run)
    db.commit()
    return {"run_id": run_id, "deleted": removed}
