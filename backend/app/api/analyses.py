"""Analyses: what can be run, running it, and the history of runs.

The params schema comes from the method's pydantic model, so the UI form is generated rather than
hand-written — a new method needs no frontend work.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import SessionLocal, get_db
from app.models.run import Run
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

    run = Run(
        id=__import__("uuid").uuid4().hex,
        kind=method,
        title=spec.display_name,
        params=parsed.model_dump(mode="json"),
        status="pending",
        created_by=getattr(user, "login", None),
    )
    db.add(run)
    db.commit()
    # 后台跑：参数量级已经在方法内部按块处理，跑起来是几分钟的事，不必让用户去 shell 里执行命令。
    _execute_in_background(run.id, method, parsed.model_dump(mode="json"), body.get("dataset") or {},
                           body.get("source_id"), body.get("display_name"),
                           getattr(user, "login", None))
    # 需要隔离执行时（内存吃紧），可以把下面的命令交给独立进程/Job 跑。

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


def _execute_in_background(run_id, method, params, dataset, source_id, display_name, created_by) -> None:
    """不再在这里执行：记录已经是 pending，由 worker 进程认领（见 app/analysis/worker.py）。

    训练与导出要几 GB 内存，跑在 API 容器里会把接口一起拖死；分开之后各有预算、互不影响。
    """
    return None


@router.get("/runs")
def list_runs(limit: int = 50, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    runs = (
        db.query(Run)
        .filter(Run.kind.notin_(("simulation", "factor_compute", "screen", "portfolio_screen")))
        .order_by(Run.started_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "runs": [
            {
                "id": run.id,
                "method": run.kind,
                "params": run.params or {},
                "dataset": {},
                "status": run.status,
                "source_id": (run.result or {}).get("source_id"),
                "artifact_sha256": run.artifact_sha256,
                "error": run.error,
                "code_revision": None,
                "created_at": run.started_at.isoformat() if run.started_at else None,
                "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            }
            for run in runs
        ]
    }


@router.get("/runs/{run_id}")
def get_run(run_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "id": run.id,
        "method": run.kind,
        "params": run.params or {},
        "status": run.status,
        "source_id": (run.result or {}).get("source_id"),
        "artifact_key": run.artifact_key,
        "artifact_sha256": run.artifact_sha256,
        "error": run.error,
    }
