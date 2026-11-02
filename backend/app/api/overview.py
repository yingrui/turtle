"""概览：一屏回答"今天需要你决定什么"。

数据到哪一天、持仓有没有异常、我的方法今天选出什么、有没有失败的任务。这四件事分散在四个页面里，
但每天早上都要一起看，所以在这里拼起来。
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.job import Job
from app.models.portfolio import Portfolio
from app.models.ranking import RankingSource
from app.models.simulation import SimulationDaily, SimulationHolding, SimulationPool, SimulationRun
from app.models.user import User

router = APIRouter(prefix="/api/overview", tags=["overview"], dependencies=[Depends(get_current_user)])


def _latest_market_day(db: Session) -> str | None:
    from app.core.tushare_schema import tushare_table

    return db.execute(text(f"SELECT max(trade_date) FROM {tushare_table('stock_trade_daily')}")).scalar()


@router.get("")
def overview(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    market_day = _latest_market_day(db)
    # Prefer the portfolio that is actually following a backtest: it is the one with something to show.
    portfolio = db.scalars(
        select(Portfolio).order_by(Portfolio.active_run_id.is_(None), Portfolio.created_at)
    ).first()
    run = None
    if portfolio is not None and portfolio.active_run_id:
        run = db.get(SimulationRun, portfolio.active_run_id)

    holdings = []
    alarms = []
    if run is not None:
        day = db.scalar(
            select(func.max(SimulationHolding.trade_date)).where(SimulationHolding.run_id == run.id)
        )
        if day is not None:
            rows = db.scalars(
                select(SimulationHolding).where(
                    SimulationHolding.run_id == run.id, SimulationHolding.trade_date == day
                )
            ).all()
            in_pool = {
                code
                for code in db.scalars(
                    select(SimulationPool.ts_code).where(
                        SimulationPool.run_id == run.id, SimulationPool.trade_date == day
                    )
                ).all()
            }
            equity = db.scalar(
                select(SimulationDaily).where(
                    SimulationDaily.run_id == run.id, SimulationDaily.trade_date == day
                )
            )
            for row in rows:
                holdings.append(
                    {
                        "ts_code": row.ts_code,
                        "shares": row.shares,
                        "price": float(row.price or 0),
                        "weight": None if row.weight is None else float(row.weight),
                    }
                )
                if in_pool and row.ts_code not in in_pool:
                    alarms.append({"ts_code": row.ts_code, "reason": "out_of_pool"})
            holdings_meta = {
                "day": day.isoformat(),
                "count": len(rows),
                "market_value": sum(float(row.market_value or 0) for row in rows),
                "cash": None if equity is None or equity.balance is None else float(equity.balance),
                "total": None if equity is None or equity.total is None else float(equity.total),
            }
        else:
            holdings_meta = None
    else:
        holdings_meta = None

    picks = []
    picks_day = None
    if run is not None and holdings_meta:
        picks_day = holdings_meta["day"]
    elif market_day is not None:
        picks_day = str(market_day)
    from app.services.analysis_service import RankingSourceService

    service = RankingSourceService()
    for source in db.scalars(
        select(RankingSource).where(RankingSource.status == "published").limit(3)
    ).all():
        top: list[dict] = []
        if picks_day:
            try:
                top = service.preview(db, source.id, date.fromisoformat(picks_day), limit=5)
            except Exception:  # noqa: BLE001 — a broken source must not blank the whole overview
                top = []
        picks.append(
            {"source_id": source.id, "name": source.display_name, "day": picks_day, "top": top}
        )

    failed_jobs = db.scalar(select(func.count()).select_from(Job).where(Job.status == "failed")) or 0

    return {
        "market_day": None if market_day is None else str(market_day),
        "portfolio": None if portfolio is None else {
            "name": portfolio.name,
            "run_id": None if run is None else run.id,
            "run_name": None if run is None else (run.name or run.id[:8]),
            "book": holdings_meta,
        },
        "alarms": alarms,
        "methods": picks,
        "failed_jobs": int(failed_jobs),
    }
