"""统一的运行记录。

回测、因子计算、评分模型、导出训练集 —— 都是"一次后台执行"，统一记在 `runs` 表里。
旧表（jobs / analysis_runs）过渡期内仍在写，但界面只读这一张。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.run import Run
from app.models.user import User

router = APIRouter(prefix="/api/tasks", tags=["tasks"], dependencies=[Depends(get_current_user)])


@router.get("")
def list_tasks(
    limit: int = Query(100, ge=1, le=500),
    status: str | None = None,
    kind: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
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
