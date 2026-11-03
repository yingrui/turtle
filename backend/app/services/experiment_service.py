"""Expand an experiment into runs, and judge it against its own controls.

The statistical gate lives here rather than in a report: a verdict is stored with the noise band it was
measured against, so "beats the controls by 2σ" is a fact about the record, not a claim in prose.
"""

from __future__ import annotations

import statistics
import uuid

from sqlalchemy.orm import Session

from app.models.experiment import Experiment, ExperimentRun
from app.models.simulation import SimulationRun


class ExperimentService:
    def create(self, db: Session, payload: dict, created_by: str | None = None) -> Experiment:
        if not payload.get("controls"):
            raise ValueError("an experiment needs at least one control: a verdict without controls is not a verdict")
        experiment = Experiment(
            id=payload.get("id") or f"exp-{uuid.uuid4().hex[:8]}",
            question=payload["question"],
            hypothesis=payload.get("hypothesis") or {},
            variants=payload.get("variants") or [],
            controls=payload.get("controls") or [],
            label=payload.get("label") or {},
            strategy=payload.get("strategy") or "pool_entry",
            window_start=payload.get("window_start"),
            window_end=payload.get("window_end"),
            portfolio=payload.get("portfolio"),
            status="draft",
            created_by=created_by,
        )
        db.add(experiment)
        db.commit()
        return experiment

    def cells(self, experiment: Experiment) -> list[tuple[str, dict, bool]]:
        """`(variant name, spec, is_control)` — the matrix, controls last."""
        return [
            *[(item["name"], item, False) for item in experiment.variants],
            *[(item["name"], item, True) for item in experiment.controls],
        ]

    def expand(self, db: Session, experiment: Experiment, *, buy_rule: str | None = None,
               portfolio: str | None = None, launched_by: str | None = None) -> list[dict]:
        """Create one simulation job per cell, and remember which job belongs to which cell.

        Expanding is a single action because the matrix is the point: variants and their controls must
        run under the same window, label and strategy, or the comparison is meaningless.
        """
        import json as _json

        from app.services.job_service import JobService

        launched = []
        for variant, spec, is_control in self.cells(experiment):
            payload = {
                "type": "simulation",
                "mode": "model",
                "buy_rule": buy_rule or experiment.strategy,
                "portfolio": portfolio or experiment.portfolio or "top50-sim",
                "ranking_source_id": spec.get("ranking_source_id"),
                "start_date": experiment.window_start,
                "end_date": experiment.window_end,
                "retrain": "none",
                "name": f"{experiment.id}:{variant}",
                "description": f"{experiment.question} · {'对照' if is_control else '变体'}",
            }
            if not payload["ranking_source_id"] or not payload["start_date"]:
                raise ValueError(f"cell {variant} is missing a ranking source or a window")
            job = JobService().create_job(db, "simulation", payload)
            self.attach(db, experiment.id, variant, job_id=job.id, is_control=is_control)
            launched.append({"variant": variant, "job_id": job.id, "is_control": is_control})
        experiment.status = "running"
        db.commit()
        return launched

    def attach(self, db: Session, experiment_id: str, variant: str, *, job_id: str | None = None,
               run_id: str | None = None, is_control: bool = False) -> ExperimentRun:
        cell = db.get(ExperimentRun, (experiment_id, variant))
        if cell is None:
            cell = ExperimentRun(experiment_id=experiment_id, variant=variant, is_control=is_control)
            db.add(cell)
        if job_id:
            cell.job_id = job_id
        if run_id:
            cell.run_id = run_id
        db.commit()
        return cell

    def summary(self, db: Session, experiment: Experiment) -> dict:
        """Excess per cell, plus the control distribution the verdict is measured against."""
        rows = []
        for cell in db.query(ExperimentRun).filter(ExperimentRun.experiment_id == experiment.id).all():
            run = db.get(SimulationRun, cell.run_id) if cell.run_id else None
            rows.append(
                {
                    "variant": cell.variant,
                    "is_control": bool(cell.is_control),
                    "run_id": cell.run_id,
                    "status": "missing" if run is None else ("completed" if run.finished_at else "running"),
                    "excess_pct": None if run is None else (
                        None if run.return_rate_pct is None else float(run.return_rate_pct)
                    ),
                    "trades": None if run is None else run.trade_count,
                }
            )
        controls = [row["excess_pct"] for row in rows if row["is_control"] and row["excess_pct"] is not None]
        spread = None
        if len(controls) >= 2:
            spread = {"mean": statistics.mean(controls), "sd": statistics.stdev(controls), "n": len(controls)}
        verdict = {}
        if spread and spread["sd"]:
            for row in rows:
                if row["is_control"] or row["excess_pct"] is None:
                    continue
                row["sigma"] = round((row["excess_pct"] - spread["mean"]) / spread["sd"], 2)
        return {
            "id": experiment.id,
            "question": experiment.question,
            "status": experiment.status,
            "strategy": experiment.strategy,
            "window": [experiment.window_start, experiment.window_end],
            "label": experiment.label or {},
            "cells": rows,
            "controls": spread,
            "conclusion": experiment.conclusion or {},
        }

    def conclude(self, db: Session, experiment: Experiment, conclusion: dict) -> Experiment:
        """A verdict requires the controls to have run: the gate, not a convention."""
        ran_controls = [
            cell for cell in db.query(ExperimentRun).filter(
                ExperimentRun.experiment_id == experiment.id, ExperimentRun.is_control.is_(True)
            ).all()
            if cell.run_id
        ]
        if not ran_controls:
            raise ValueError("cannot conclude: the control runs are missing")
        experiment.conclusion = conclusion
        experiment.status = conclusion.get("verdict") == "abandoned" and "abandoned" or "concluded"
        db.commit()
        return experiment
