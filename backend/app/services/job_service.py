import json
import threading
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.job import Job
from app.models.simulation import SimulationDaily, SimulationRun, SimulationTrade
from app.services.portfolio_service import PortfolioService
from app.core.dataset.sync import sync_stock_data, sync_trade_calendar
from app.services.screening_service import ScreeningService
from app.core.engine.InvestmentLogger import InvestmentLogger
from app.core.simulation.runner import run_simulation


class JobService:
    def create_job(self, db: Session, job_type: str, payload: dict) -> Job:
        job = Job(
            id=str(uuid.uuid4()),
            type=job_type,
            status="pending",
            payload=json.dumps(payload),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        thread = threading.Thread(target=self._run_job, args=(job.id,), daemon=True)
        thread.start()
        return job

    def _run_job(self, job_id: str) -> None:
        db = SessionLocal()
        try:
            job = db.get(Job, job_id)
            if not job:
                return
            job.status = "running"
            db.commit()
            payload = json.loads(job.payload)
            logs: list[str] = []

            def log_fn(msg: str) -> None:
                logs.append(msg)
                job.log = "\n".join(logs)
                db.commit()

            if job.type == "data_sync":
                start = date.fromisoformat(payload["from_date"])
                end = date.fromisoformat(payload.get("to_date", payload["from_date"]))
                sync_stock_data(
                    start,
                    end,
                    trade_data=payload.get("trade_data", True),
                    adj_data=payload.get("adj_data", True),
                    daily_basic=payload.get("daily_basic", True),
                    dividend=payload.get("dividend", True),
                    log_fn=log_fn,
                )
                job.result = json.dumps({"from_date": payload["from_date"], "to_date": end.isoformat()})
            elif job.type == "calendar_sync":
                start_year = int(payload["start_year"])
                end_year = int(payload.get("end_year", start_year))
                sync_trade_calendar(start_year, end_year, log_fn=log_fn)
                job.result = json.dumps({"start_year": start_year, "end_year": end_year})
            elif job.type == "portfolio_screen":
                as_of = date.fromisoformat(payload["as_of_date"])
                rows = ScreeningService().run_screen(
                    as_of,
                    ignore_st=payload.get("ignore_st", True),
                    trend_filter=payload.get("trend_filter"),
                )
                job.result = json.dumps({"count": len(rows), "stocks": rows[:500]})
                log_fn(f"Screened {len(rows)} stocks")
            elif job.type == "simulation":
                portfolio_svc = PortfolioService(db)
                config_name = payload["portfolio"]
                config = portfolio_svc.get_portfolio(config_name)
                start_date = date.fromisoformat(payload["start_date"])
                end_date = date.fromisoformat(payload.get("end_date", date.today().isoformat()))
                policy_ids = payload.get("policy_ids")
                if policy_ids is None:
                    policy_ids = list(range(len(config["policies"])))
                run_ids: list[str] = []
                portfolio_name = config.get("name", config_name)
                for policy_id in policy_ids:
                    run_id = str(uuid.uuid4())
                    run = SimulationRun(
                        id=run_id,
                        job_id=job.id,
                        portfolio_name=portfolio_name,
                        policy_id=policy_id,
                        config_snapshot=json.dumps(config, default=str),
                    )
                    db.add(run)
                    db.commit()

                    def make_on_save(rid: str):
                        def on_save(logger: InvestmentLogger) -> None:
                            self._persist_simulation_results(db, rid, logger)
                        return on_save

                    logger_name = f"{portfolio_name}-{policy_id}"
                    logger_sink = InvestmentLogger(
                        logger_name,
                        folder=settings.stock_logs_dir,
                        on_save=make_on_save(run_id),
                    )
                    run_simulation(
                        config,
                        start_date,
                        end_date,
                        policy_id,
                        logs_folder=settings.stock_logs_dir,
                        logger_sink=logger_sink,
                    )
                    run_ids.append(run_id)
                    log_fn(f"Completed policy {policy_id}")
                job.result = json.dumps({"run_ids": run_ids})
            else:
                raise ValueError(f"Unknown job type: {job.type}")

            job.status = "completed"
            job.log = "\n".join(logs)
            db.commit()
        except Exception as exc:
            job = db.get(Job, job_id)
            if job:
                job.status = "failed"
                job.error = str(exc)
                db.commit()
        finally:
            db.close()

    def _persist_simulation_results(self, db: Session, run_id: str, logger: InvestmentLogger) -> None:
        run = db.get(SimulationRun, run_id)
        if not run:
            return
        for _, row in logger.get_daily_log().iterrows():
            trade_date = row["date"]
            if hasattr(trade_date, "date"):
                trade_date = trade_date.date()
            db.add(
                SimulationDaily(
                    run_id=run_id,
                    trade_date=trade_date,
                    return_rate=Decimal(str(row["return_rate"])),
                    balance=Decimal(str(row["balance"])),
                    benefit=Decimal(str(row["benefit"])),
                    investment_total=Decimal(str(row["investment_total"])),
                    total=Decimal(str(row["total"])),
                )
            )
        for _, row in logger.get_trade_log().iterrows():
            hold_date = row.get("hold_date")
            if hold_date is not None and hasattr(hold_date, "date"):
                hold_date = hold_date.date()
            trade_date = row["date"]
            if hasattr(trade_date, "date"):
                trade_date = trade_date.date()
            db.add(
                SimulationTrade(
                    run_id=run_id,
                    trade_date=trade_date,
                    ts_code=row["ts_code"],
                    hold_shares=int(row["hold_shares"]),
                    hold_date=hold_date,
                    buy_price=Decimal(str(row["buy_price"])) if row.get("buy_price") is not None and str(row["buy_price"]) != "nan" else None,
                    sell_price=Decimal(str(row["sell_price"])) if row.get("sell_price") is not None and str(row["sell_price"]) != "nan" else None,
                    total_cash_return=Decimal(str(row["total_cash_return"])) if row.get("total_cash_return") is not None and str(row["total_cash_return"]) != "nan" else None,
                    benefit=Decimal(str(row["benefit"])) if row.get("benefit") is not None and str(row["benefit"]) != "nan" else None,
                    reason=str(row.get("reason", "")),
                    status=str(row["status"]),
                )
            )
        run.finished_at = datetime.utcnow()
        db.commit()
