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
    """把分析交给**独立子进程**执行。

    训练/导出要拉 1.5 年的因子面板，放在 API 进程里会把整个服务一起 OOM 掉（已经发生过）。子进程至少
    让崩溃只影响这一个任务；进度与结果由子进程自己写回 runs。
    """
    import json
    import subprocess
    import sys

    command = [
        sys.executable, "-m", "app.analysis.run",
        "--method", method,
        "--run-id", run_id,
        "--params", json.dumps(params, ensure_ascii=False),
        "--dataset", json.dumps(dataset or {}, ensure_ascii=False),
    ]
    if source_id:
        command += ["--source-id", str(source_id)]
    if display_name:
        command += ["--display-name", str(display_name)]
    if created_by:
        command += ["--created-by", str(created_by)]
    # 不等待：父进程只负责派活，日志与状态由子进程写进 runs。
    subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


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
