"""一次执行的生命周期：开始、完成、失败。两条旧路径都调它，保证记录一致。

旧表（jobs / analysis_runs）仍在写；这里是新增的一份，等读路径切过来、历史回填完，再删旧的。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

import contextvars

from app.models.run import Run

#: 当前线程正在跑哪条 runs 记录。方法内部不需要知道 run_id，用它上报进度即可。
CURRENT_RUN: contextvars.ContextVar[str | None] = contextvars.ContextVar("current_run", default=None)

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


def append_log(db: Session, run_id: str, line: str) -> None:
    """日志按行追加到 runs.log；找不到记录就静默跳过（双写过渡期的旧记录）。"""
    run = db.get(Run, run_id)
    if run is None:
        return
    run.log = f"{run.log}\n{line}" if run.log else line
    db.commit()


def set_progress(db: Session, run_id: str, text: str) -> None:
    run = db.get(Run, run_id)
    if run is None:
        return
    run.progress = text[:255]
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


def mark_interrupted(db: Session) -> int:
    """服务重启时收尾：线程没了，记录不能一直显示"运行中"。"""
    stuck = db.query(Run).filter(Run.status.in_(("pending", "running"))).all()
    for run in stuck:
        run.status = "failed"
        run.error = "运行被中断（服务重启）；请重新发起"
        run.finished_at = datetime.utcnow()
    if stuck:
        db.commit()
    return len(stuck)


def report_progress(detail: str, percent: int | None = None) -> None:
    """由任务自己调用：把进度写到 runs.progress，界面上就能看到百分比变化。

    不写也不算错 —— 没上报的任务在完成时从 0 直接变 100。
    """
    run_id = CURRENT_RUN.get()
    if not run_id:
        return
    from app.database import SessionLocal

    label = f"{percent}% · {detail}" if percent is not None else detail
    with SessionLocal() as db:
        run = db.get(Run, run_id)
        if run is None:
            return
        run.progress = label[:255]
        db.commit()
