"""Analyses: what can be run, running it, and the history of runs.

The params schema comes from the method's pydantic model, so the UI form is generated rather than
hand-written — a new method needs no frontend work.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import SessionLocal, get_db
from app.models.ranking import AnalysisRun
from app.models.user import User
from app.services.analysis_service import run_analysis

router = APIRouter(prefix="/api/analyses", tags=["analyses"], dependencies=[Depends(get_current_user)])


@router.get("")
def list_methods(_: User = Depends(get_current_user)):
    from app.analysis import registry
    from app.analysis import methods  # noqa: F401  (registration side effect)

    return {"methods": registry.describe()}


@router.post("/{method}/runs")
def start_run(
    method: str,
    body: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from app.analysis import registry
    from app.analysis import methods  # noqa: F401

    try:
        spec = registry.get(method)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown method: {method}") from None
    try:
        parsed = spec.params_model(**(body.get("params") or {}))
    except Exception as exc:  # noqa: BLE001 — validation errors are user errors
        raise HTTPException(status_code=422, detail=str(exc)) from None

    run = AnalysisRun(
        id=__import__("uuid").uuid4().hex,
        method=method,
        params=parsed.model_dump(mode="json"),
        dataset_name=(body.get("dataset") or {}).get("name"),
        dataset_version=(body.get("dataset") or {}).get("version"),
        status="pending",
        created_by=user.login if hasattr(user, "login") else None,
    )
    db.add(run)
    db.commit()
    # Not in this process: a full-window run needs more memory than the API pod has (see
    # app/analysis/run.py). The command is returned so a worker/Job can execute it.
    command = [
        "python", "-m", "app.analysis.run",
        "--method", method,
        "--run-id", run.id,
        "--params", __import__("json").dumps(parsed.model_dump(mode="json")),
        "--dataset", __import__("json").dumps(body.get("dataset") or {}),
    ]
    if body.get("source_id"):
        command += ["--source-id", str(body["source_id"])]
    if body.get("display_name"):
        command += ["--display-name", str(body["display_name"])]
    return {"run_id": run.id, "status": "pending", "command": command}


@router.get("/runs")
def list_runs(limit: int = 50, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    runs = db.query(AnalysisRun).order_by(AnalysisRun.created_at.desc()).limit(limit).all()
    return {
        "runs": [
            {
                "id": run.id,
                "method": run.method,
                "params": run.params or {},
                "dataset": {"name": run.dataset_name, "version": run.dataset_version},
                "status": run.status,
                "source_id": run.source_id,
                "artifact_sha256": run.artifact_sha256,
                "error": run.error,
                "code_revision": run.code_revision,
                "created_at": run.created_at.isoformat() if run.created_at else None,
                "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            }
            for run in runs
        ]
    }


@router.get("/runs/{run_id}")
def get_run(run_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    run = db.get(AnalysisRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "id": run.id,
        "method": run.method,
        "params": run.params or {},
        "status": run.status,
        "source_id": run.source_id,
        "artifact_key": run.artifact_key,
        "artifact_sha256": run.artifact_sha256,
        "error": run.error,
    }
