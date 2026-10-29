import json

import pandas as pd
import threading
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.job import Job
from app.models.simulation import SimulationDaily, SimulationRun, SimulationTrade
from app.services.portfolio_service import PortfolioService
from app.services.factor_service import FactorError, FactorService
from app.services.screening_service import ScreeningService
from app.core.engine.InvestmentLogger import InvestmentLogger
from app.core.simulation.runner import run_simulation
from app.core.util.simulation_analysis import summarize_run


def _provenance(payload: dict, *, policy: str | None, source: str) -> dict:
    """The recipe of a run, in the shape an experiment report can quote verbatim."""
    provenance: dict = {"ranking": {"source": source}}
    if policy:
        provenance["ranking"]["policy"] = policy
    for key in ("dataset", "dataset_version", "dataset_sha256", "label", "horizon", "benchmark"):
        if payload.get(key) is not None:
            group = {
                "dataset": "dataset",
                "dataset_version": "dataset",
                "dataset_sha256": "dataset",
                "label": "label",
                "horizon": "label",
                "benchmark": "label",
            }[key]
            name = {"dataset": "name", "dataset_version": "version",
                    "dataset_sha256": "manifest_sha256", "label": "kind",
                    "horizon": "horizon", "benchmark": "benchmark"}[key]
            provenance.setdefault(group, {})[name] = payload[key]
    return provenance


def _decimal_or_none(value) -> Decimal | None:
    if value is None or str(value) == "nan" or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


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

    def mark_interrupted(self, db: Session) -> int:
        """Close out jobs a previous process left behind.

        Jobs run as threads inside this process, so a restart — a deploy, a reload, an OOM kill —
        abandons whatever was in flight. Without this the row keeps saying ``running`` and the UI
        polls something that will never finish. Called once at startup.
        """
        jobs = db.query(Job).filter(Job.status.in_(("pending", "running"))).all()
        for job in jobs:
            job.status = "failed"
            job.error = "Interrupted: the API process restarted while this job was running."
        db.commit()
        return len(jobs)

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

            if job.type == "portfolio_screen":
                as_of = date.fromisoformat(payload["as_of_date"])
                rows = ScreeningService().run_screen(
                    as_of,
                    ignore_st=payload.get("ignore_st", True),
                    trend_filter=payload.get("trend_filter"),
                )
                job.result = json.dumps({"count": len(rows), "stocks": rows[:500]})
                log_fn(f"Screened {len(rows)} stocks")
            elif job.type == "simulation" and payload.get("mode") == "model":
                from app.core.simulation.model_runner import ModelRunConfig, run_model_simulation, summarise

                config = ModelRunConfig(
                    policy=payload.get("model_policy", "expanding"),
                    top_n=int(payload.get("top_n", 50)),
                    sell_rank_limit=payload.get("sell_rank_limit"),
                    max_holding_days=payload.get("max_holding_days"),
                    cash_buffer=float(payload.get("cash_buffer", 0.05)),
                )
                start_date = date.fromisoformat(payload["start_date"])
                end_date = date.fromisoformat(payload.get("end_date", date.today().isoformat()))
                portfolio_svc = PortfolioService(db)
                portfolio_name = payload["portfolio"]
                portfolio_id = portfolio_svc.get_portfolio_id(portfolio_name)
                initial_cash = float(payload.get("initial_cash") or 1_000_000)
                run = SimulationRun(
                    id=str(uuid.uuid4()),
                    job_id=job.id,
                    portfolio_id=portfolio_id,
                    portfolio_name=portfolio_name,
                    policy_id=0,
                    mode="model",
                    pool_mode="dynamic",
                    name=payload.get("name"),
                    description=payload.get("description"),
                    config_snapshot=json.dumps(
                        {"kind": "model", "portfolio": portfolio_name, **config.as_dict(),
                         "initial_cash": initial_cash,
                         "start_date": start_date.isoformat(), "end_date": end_date.isoformat()}
                    ),
                )
                db.add(run)
                db.commit()
                log_fn(f"model run {run.id}: {start_date} … {end_date}, {config.top_n} names")

                def report(day, equity, cash, names):
                    log_fn(f"{day}: equity {equity:,.0f} · cash {cash:,.0f} · {names} names")

                result = run_model_simulation(
                    db, run=run, start=start_date, end=end_date,
                    initial_cash=initial_cash, config=config, on_day=report,
                )
                summary = summarise(db, run.id)
                for field_name, value in summary.items():
                    setattr(run, field_name, value)
                run.finished_at = datetime.utcnow()
                db.commit()
                job.result = json.dumps({
                    "run_id": run.id,
                    "mode": "model",
                    "days": result.days,
                    "trades": result.trades,
                    "holdings_rows": result.holdings_rows,
                    "final_equity": round(result.final_equity, 2),
                    "skipped_days": result.skipped_days[:10],
                })
                log_fn(f"done: {result.days} days, {result.trades} fills, final {result.final_equity:,.0f}")
            elif job.type == "simulation":
                portfolio_svc = PortfolioService(db)
                config_name = payload["portfolio"]
                config = dict(portfolio_svc.get_portfolio(config_name))
                ts_codes = payload.get("ts_codes")
                if ts_codes:
                    config["follow_stocks"] = list(ts_codes)
                start_date = date.fromisoformat(payload["start_date"])
                end_date = date.fromisoformat(payload.get("end_date", date.today().isoformat()))
                policy_ids = payload.get("policy_ids")
                if policy_ids is None:
                    policy_ids = list(range(len(config["policies"])))
                run_ids: list[str] = []
                portfolio_name = config.get("name", config_name)
                portfolio_id = portfolio_svc.get_portfolio_id(config_name)
                for policy_id in policy_ids:
                    run_id = str(uuid.uuid4())
                    run = SimulationRun(
                        id=run_id,
                        job_id=job.id,
                        portfolio_id=portfolio_id,
                        portfolio_name=portfolio_name,
                        policy_id=policy_id,
                        mode="signal",
                        name=payload.get("name"),
                        description=payload.get("description"),
                        # A signal run's pool is the configured watchlist, the same list every day; it is
                        # read from the config snapshot rather than duplicated into `simulation_pool`.
                        pool_mode="fixed",
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
                job.result = json.dumps({
                    "run_ids": run_ids,
                    "ts_codes_count": len(config.get("follow_stocks") or []),
                    "portfolio": config_name,
                })
            elif job.type == "factor_compute":
                service = FactorService()
                codes = payload.get("codes") or [payload["code"]]
                start = date.fromisoformat(payload["start"]) if payload.get("start") else None
                end = date.fromisoformat(payload["end"]) if payload.get("end") else None
                results = []
                for code in codes:
                    try:
                        result = service.compute(db, code, start=start, end=end, log=log_fn)
                    except FactorError as exc:
                        log_fn(f"{code}: {exc}")
                        continue
                    results.append(result)
                    log_fn(
                        f"{code}: {result['rows_written']} values, "
                        f"{result['stocks']} stocks, {result['dates']} days"
                    )
                job.result = json.dumps({"factors": results})
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
        # Trades land in the shared ledger, tagged with the run. Daily holding snapshots from
        # the simulator are skipped: positions are replayable from buys/sells.
        stored_trades: list[dict] = []
        if run.portfolio_id:
            for _, row in logger.get_trade_log().iterrows():
                if str(row.get("status")) not in ("buy", "win", "loss"):
                    continue
                trade_date = row["date"]
                if hasattr(trade_date, "date"):
                    trade_date = trade_date.date()
                side = "buy" if str(row.get("status")) == "buy" else "sell"
                shares = int(row["hold_shares"])
                price = _decimal_or_none(row.get("buy_price")) if side == "buy" else _decimal_or_none(row.get("sell_price"))
                if price is None:
                    continue
                if side == "sell":
                    realized = _decimal_or_none(row.get("benefit"))
                else:
                    realized = None
                stored_trades.append(
                    {
                        "ts_code": str(row["ts_code"]),
                        "side": side,
                        "shares": int(row["hold_shares"]),
                        "benefit": float(realized) if realized is not None else 0.0,
                    }
                )
                db.add(
                    SimulationTrade(
                        id=str(uuid.uuid4()),
                        run_id=run_id,
                        ts_code=str(row["ts_code"]),
                        trade_date=trade_date,
                        side=side,
                        shares=shares,
                        price=price,
                        amount=(price * shares).quantize(Decimal("0.01")),
                        realized_pnl=_decimal_or_none(row.get("benefit")) if side == "sell" else None,
                        reason=str(row.get("reason") or ""),
                    )
                )
        # The summary is stored, not recomputed per read: the ontology mirrors this row, and a
        # reader should not have to replay the daily log to learn how the run did.
        summary = summarize_run(run.policy_id, logger.get_daily_log(), pd.DataFrame(stored_trades))
        for field, value in summary.items():
            setattr(run, field, value)
        run.finished_at = datetime.utcnow()
        db.commit()
