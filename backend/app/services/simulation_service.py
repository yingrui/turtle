import json

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.simulation import SimulationDaily, SimulationRun, SimulationTrade
from app.core.util import chart_data
from app.core.util.json_utils import dataframe_to_records
from app.core.util.simulation_analysis import calculate_cagr, get_stock_benefit, load_simulation_logs_from_disk


class SimulationService:
    def list_runs(self, db: Session, job_id: str | None = None) -> list[dict]:
        stmt = select(SimulationRun).order_by(SimulationRun.started_at.desc())
        if job_id:
            stmt = stmt.where(SimulationRun.job_id == job_id)
        runs = db.scalars(stmt).all()
        return [
            {
                "id": r.id,
                "job_id": r.job_id,
                "portfolio_name": r.portfolio_name,
                "policy_id": r.policy_id,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            }
            for r in runs
        ]

    def compare_job_runs(self, db: Session, job_id: str) -> list[dict]:
        runs = self.list_runs(db, job_id=job_id)
        out = []
        for run in runs:
            try:
                summary = self.get_summary(db, run["id"])
                out.append({**run, **summary})
            except FileNotFoundError:
                continue
        return out

    def get_win_loss(self, db: Session, run_id: str) -> dict:
        df = self.get_trades_from_db(db, run_id)
        if df.empty:
            run = db.get(SimulationRun, run_id)
            config = json.loads(run.config_snapshot)
            _, df_trade_list, _ = load_simulation_logs_from_disk(
                run.portfolio_name, run.policy_id + 1, config["follow_stocks"], settings.stock_logs_dir
            )
            df = df_trade_list[run.policy_id]
        closed = df[df["status"].isin(["win", "loss"])]
        return {
            "win": int((closed["status"] == "win").sum()),
            "loss": int((closed["status"] == "loss").sum()),
            "holding": int((df["status"] == "holding").sum()),
        }

    def get_daily_from_db(self, db: Session, run_id: str) -> pd.DataFrame:
        rows = db.scalars(
            select(SimulationDaily).where(SimulationDaily.run_id == run_id).order_by(SimulationDaily.trade_date)
        ).all()
        return pd.DataFrame(
            [
                {
                    "date": r.trade_date,
                    "return_rate": float(r.return_rate),
                    "balance": float(r.balance),
                    "benefit": float(r.benefit),
                    "investment_total": float(r.investment_total),
                    "total": float(r.total),
                }
                for r in rows
            ]
        )

    def get_trades_from_db(self, db: Session, run_id: str) -> pd.DataFrame:
        rows = db.scalars(select(SimulationTrade).where(SimulationTrade.run_id == run_id)).all()
        return pd.DataFrame(
            [
                {
                    "date": r.trade_date,
                    "ts_code": r.ts_code,
                    "hold_shares": r.hold_shares,
                    "hold_date": r.hold_date,
                    "buy_price": float(r.buy_price) if r.buy_price is not None else None,
                    "sell_price": float(r.sell_price) if r.sell_price is not None else None,
                    "total_cash_return": float(r.total_cash_return) if r.total_cash_return is not None else None,
                    "benefit": float(r.benefit) if r.benefit is not None else None,
                    "reason": r.reason,
                    "status": r.status,
                }
                for r in rows
            ]
        )

    def get_summary(self, db: Session, run_id: str) -> dict:
        run = db.get(SimulationRun, run_id)
        if not run:
            raise FileNotFoundError("Run not found")
        df = self.get_daily_from_db(db, run_id)
        if df.empty:
            config = json.loads(run.config_snapshot)
            df_list, _, _ = load_simulation_logs_from_disk(
                run.portfolio_name,
                run.policy_id + 1,
                config["follow_stocks"],
                settings.stock_logs_dir,
            )
            df = df_list[run.policy_id]
        return calculate_cagr(run.policy_id, df)

    def get_daily_chart(self, db: Session, run_id: str) -> dict:
        df = self.get_daily_from_db(db, run_id)
        if df.empty:
            run = db.get(SimulationRun, run_id)
            config = json.loads(run.config_snapshot)
            df_list, _, _ = load_simulation_logs_from_disk(
                run.portfolio_name, run.policy_id + 1, config["follow_stocks"], settings.stock_logs_dir
            )
            df = df_list[run.policy_id]
        return chart_data.investment_log_chart(df)

    def get_trades(self, db: Session, run_id: str, limit: int = 60) -> list[dict]:
        df = self.get_trades_from_db(db, run_id)
        if df.empty:
            run = db.get(SimulationRun, run_id)
            config = json.loads(run.config_snapshot)
            _, df_trade_list, _ = load_simulation_logs_from_disk(
                run.portfolio_name, run.policy_id + 1, config["follow_stocks"], settings.stock_logs_dir
            )
            df = df_trade_list[run.policy_id]
        df = df.tail(limit)
        return dataframe_to_records(df.reset_index(drop=True))

    def get_benefit_by_stock(self, db: Session, run_id: str) -> list[dict]:
        df_trades = self.get_trades_from_db(db, run_id)
        run = db.get(SimulationRun, run_id)
        if df_trades.empty:
            config = json.loads(run.config_snapshot)
            _, df_trade_list, df_benefit = load_simulation_logs_from_disk(
                run.portfolio_name, run.policy_id + 1, config["follow_stocks"], settings.stock_logs_dir
            )
            return dataframe_to_records(df_benefit)
        benefit = get_stock_benefit(run.policy_id, df_trades)
        return dataframe_to_records(benefit.reset_index())
