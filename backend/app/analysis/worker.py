"""独立执行分析任务的 worker。

训练与导出要几 GB 内存，跑在 API 容器里会把接口一起拖死。这里把它拆出来：API 只写一条 pending 记录，
worker 认领、执行、写回结果。两者各有自己的内存预算。

    python -m app.analysis.worker --poll-seconds 5
"""

from __future__ import annotations

import argparse
import time

from sqlalchemy import text

from app.analysis import methods  # noqa: F401  (注册方法)
from app.database import SessionLocal
from app.services.analysis_service import run_analysis
from app.services.run_service import CURRENT_RUN

ANALYSIS_KINDS = ("scorecard_train", "regime_score", "constant_pool", "dataset_build")


def claim_one(db):
    """认领一条待执行的分析任务；并发下用 SKIP LOCKED 避免两个 worker 抢同一条。"""
    row = db.execute(
        text(
            "UPDATE runs SET status = 'running', heartbeat_at = now() "
            "WHERE id = ("
            "  SELECT id FROM runs WHERE status = 'pending' AND kind = ANY(:kinds) "
            "  ORDER BY started_at LIMIT 1 FOR UPDATE SKIP LOCKED"
            ") RETURNING id, kind, params"
        ),
        {"kinds": list(ANALYSIS_KINDS)},
    ).first()
    db.commit()
    return row


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--poll-seconds", type=int, default=5)
    args = parser.parse_args(argv)

    print(f"worker 启动，轮询间隔 {args.poll_seconds}s，处理 {', '.join(ANALYSIS_KINDS)}", flush=True)
    while True:
        with SessionLocal() as db:
            claimed = claim_one(db)
            if claimed is None:
                time.sleep(args.poll_seconds)
                continue
            run_id, kind, params = claimed
            CURRENT_RUN.set(run_id)
            print(f"执行 {kind} {run_id}", flush=True)
            try:
                run_analysis(db, method=kind, params=params or {}, run_id=run_id)
                print(f"完成 {run_id}", flush=True)
            except Exception as exc:  # noqa: BLE001 — 失败已写进 runs
                print(f"失败 {run_id}: {exc}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
