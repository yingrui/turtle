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
    """一次分析在后台线程里跑完，结果写回同一条运行记录。"""
    import threading

    from app.database import SessionLocal
    from app.services.analysis_service import run_analysis

    def work() -> None:
        with SessionLocal() as session:
            try:
                run_analysis(
                    session,
                    method=method,
                    params=params,
                    dataset=dataset,
                    source_id=source_id,
                    display_name=display_name,
                    created_by=created_by,
                    run_id=run_id,
                )
            except Exception:  # noqa: BLE001 — 失败原因已经写在运行记录里
                pass

    threading.Thread(target=work, daemon=True).start()


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
