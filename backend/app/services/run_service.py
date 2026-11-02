"""一次执行的生命周期：开始、完成、失败。两条旧路径都调它，保证记录一致。

旧表（jobs / analysis_runs）仍在写；这里是新增的一份，等读路径切过来、历史回填完，再删旧的。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.run import Run

JOB_TITLES = {"simulation": "回测", "factor_compute": "因子计算", "screen": "选股计算"}
ANALYSIS_TITLES = {
    "dataset_build": "导出训练集",
    "scorecard_train": "训练评分卡",
    "regime_score": "生成评分模型",
    "constant_pool": "生成对照池",
}


def start_run(
    db: Session,
    *,
    run_id: str,
    kind: str,
    params: dict | None = None,
    title: str | None = None,
    created_by: str | None = None,
) -> Run:
    if db.get(Run, run_id) is not None:
        return db.get(Run, run_id)  # 双写时重复调用不算错误
    run = Run(
        id=run_id,
        kind=kind,
        title=title or ANALYSIS_TITLES.get(kind) or JOB_TITLES.get(kind) or kind,
        status="pending",
        params=params or {},
        created_by=created_by,
    )
    db.add(run)
    db.commit()
    return run


def mark_running(db: Session, run_id: str) -> None:
    run = db.get(Run, run_id)
    if run is None:
        return
    run.status = "running"
    db.commit()


def finish_run(
    db: Session, run_id: str, *, status: str, result: dict | None = None, error: str | None = None
) -> None:
    run = db.get(Run, run_id)
    if run is None:
        return
    run.status = status
    run.result = result or {}
    run.error = error
    run.finished_at = datetime.utcnow()
    db.commit()
