"""统一的运行记录。

回测、因子计算、评分模型、导出训练集 —— 在系统眼里都是"一次后台执行"，有状态、有结果、会失败。
它们现在分存在 jobs 与 analysis_runs 两张表里（历史原因），这里合成一个列表，界面上只需要看一处。
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.job import Job
from app.models.ranking import AnalysisRun
from app.models.user import User

router = APIRouter(prefix="/api/tasks", tags=["tasks"], dependencies=[Depends(get_current_user)])

JOB_TITLES = {
    "simulation": "回测",
    "factor_compute": "因子计算",
    "screen": "选股计算",
}


def _job_title(job: Job) -> str:
    try:
        payload = json.loads(job.payload or "{}")
    except json.JSONDecodeError:
        payload = {}
    name = payload.get("name")
    base = JOB_TITLES.get(job.type, job.type)
    return f"{base}：{name}" if name else base


def _analysis_title(run: AnalysisRun) -> str:
    names = {
        "dataset_build": "导出训练集",
        "scorecard_train": "训练评分卡",
        "regime_score": "生成评分模型",
        "constant_pool": "生成对照池",
    }
    return names.get(run.method, run.method)


@router.get("")
def list_tasks(
    limit: int = Query(100, ge=1, le=500),
    status: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    jobs = db.query(Job).order_by(Job.created_at.desc()).limit(limit).all()
    runs = db.query(AnalysisRun).order_by(AnalysisRun.created_at.desc()).limit(limit).all()

    items = [
        {
            "id": job.id,
            "source": "job",
            "kind": job.type,
            "title": _job_title(job),
            "status": job.status,
            "started_at": job.created_at.isoformat() if job.created_at else None,
            "finished_at": job.updated_at.isoformat() if job.status in ("completed", "failed") and job.updated_at else None,
            "error": job.error,
            "detail": job.progress or None,
        }
        for job in jobs
    ] + [
        {
            "id": run.id,
            "source": "analysis",
            "kind": run.method,
            "title": _analysis_title(run),
            "status": run.status,
            "started_at": run.created_at.isoformat() if run.created_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "error": run.error,
            "detail": run.source_id or None,
        }
        for run in runs
    ]
    if status:
        items = [item for item in items if item["status"] == status]
    items.sort(key=lambda item: item["started_at"] or "", reverse=True)
    return {"tasks": items[:limit]}
