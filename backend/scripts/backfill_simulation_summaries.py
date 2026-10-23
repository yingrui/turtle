"""Fill `simulation_runs` summary columns for runs that predate them.

Same helper the live path uses (`summarize_run`), so a backfilled row and a fresh one cannot
disagree. Reads the run's stored daily rows and trades; skips runs that already have a summary
unless `--force`.

    python -m scripts.backfill_simulation_summaries [--force] [--dry-run]
"""

from __future__ import annotations

import argparse
from decimal import Decimal

import pandas as pd
from sqlalchemy import select

from app.core.util.simulation_analysis import summarize_run
from app.database import SessionLocal
from app.models.portfolio import PortfolioTransaction
from app.models.simulation import SimulationDaily, SimulationRun


def _daily_frame(db, run_id: str) -> pd.DataFrame:
    rows = db.scalars(
        select(SimulationDaily)
        .where(SimulationDaily.run_id == run_id)
        .order_by(SimulationDaily.trade_date)
    ).all()
    return pd.DataFrame(
        [{"date": r.trade_date, "total": float(r.total)} for r in rows]
    )


def _trade_frame(db, run_id: str) -> pd.DataFrame:
    rows = db.scalars(
        select(PortfolioTransaction).where(PortfolioTransaction.simulation_run_id == run_id)
    ).all()
    return pd.DataFrame(
        [
            {
                "ts_code": r.ts_code,
                "side": r.side,
                "shares": r.shares,
                "benefit": float(r.realized_pnl) if r.realized_pnl is not None else 0.0,
            }
            for r in rows
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="recompute rows that already have a summary")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        runs = db.scalars(select(SimulationRun).order_by(SimulationRun.started_at)).all()
        updated = 0
        for run in runs:
            if run.final_total is not None and not args.force:
                continue
            summary = summarize_run(
                run.policy_id, _daily_frame(db, run.id), _trade_frame(db, run.id)
            )
            if not summary:
                print(f"{run.id}: no daily rows, skipped")
                continue
            for field, value in summary.items():
                setattr(
                    run,
                    field,
                    Decimal(str(value)) if isinstance(value, float) else value,
                )
            updated += 1
            print(
                f"{run.id}: return {summary['return_rate_pct']}% cagr {summary['cagr']} "
                f"dd {summary['max_drawdown_pct']}% trades {summary['trade_count']}"
            )
        if args.dry_run:
            db.rollback()
        else:
            db.commit()
        print(f"{updated} run(s) summarised" + (" (dry run)" if args.dry_run else ""))
    finally:
        db.close()


if __name__ == "__main__":
    main()
