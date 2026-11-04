"""统一的运行记录。

回测、因子计算、评分模型、导出训练集 —— 都是"一次后台执行"，统一记在 `runs` 表里。
旧表（jobs / analysis_runs）过渡期内仍在写，但界面只读这一张。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.run import Run
from app.models.user import User

router = APIRouter(prefix="/api/tasks", tags=["tasks"], dependencies=[Depends(get_current_user)])


@router.post("/{task_id}/retry")
def retry_task(task_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """按原来的参数再跑一次。

    失败多半是环境问题（重启、凭据、网络），参数本身通常没问题 —— 让用户重新填一遍没有意义。
    """
    from app.api.analyses import _execute_in_background
    from app.models.run import Run as RunModel

    run = db.get(RunModel, task_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status in ("pending", "running"):
        raise HTTPException(status_code=409, detail="该运行仍在进行中")

    job_kinds = {"simulation", "factor_compute", "screen", "portfolio_screen"}
    if run.kind in job_kinds:
        from app.services.job_service import JobService

        new_run = JobService().create_job(db, run.kind, run.params or {})
        return {"run_id": new_run.id, "kind": run.kind}

    new_run = RunModel(
        id=__import__("uuid").uuid4().hex,
        kind=run.kind,
        title=run.title,
        params=run.params or {},
        status="pending",
        created_by=getattr(user, "login", None),
    )
    db.add(new_run)
    db.commit()
    _execute_in_background(
        new_run.id, run.kind, run.params or {}, {}, None, None, getattr(user, "login", None)
    )
    return {"run_id": new_run.id, "kind": run.kind}


@router.get("")
def list_tasks(
    limit: int = Query(100, ge=1, le=500),
    status: str | None = None,
    kind: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from app.services.run_service import fail_stale

    fail_stale(db, minutes=15)
    query = db.query(Run)
    if status:
        query = query.filter(Run.status == status)
    if kind:
        query = query.filter(Run.kind == kind)
    rows = query.order_by(Run.started_at.desc()).limit(limit).all()
    return {
        "tasks": [
            {
                "id": row.id,
                "kind": row.kind,
                "title": row.title or row.kind,
                "status": row.status,
                "started_at": row.started_at.isoformat() if row.started_at else None,
                "finished_at": row.finished_at.isoformat() if row.finished_at else None,
                "error": row.error,
                "detail": (row.result or {}).get("source_id"),
                "progress": row.progress or "",
            }
            for row in rows
        ]
    }
