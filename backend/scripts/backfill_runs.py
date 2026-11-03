"""把历史执行记录从 jobs / analysis_runs 回填到 runs。

幂等：按 id 去重，重复执行不会产生重复行。只写 runs，不改旧表 —— 回填失败可以重跑。

    python -m scripts.backfill_runs            # 干跑，只报数量
    python -m scripts.backfill_runs --apply
"""

from __future__ import annotations

import argparse
import json

from sqlalchemy import text

from app.database import SessionLocal
from app.models.run import Run
from app.services.run_service import ANALYSIS_TITLES, JOB_TITLES


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    with SessionLocal() as db:
        existing = {row[0] for row in db.execute(text("SELECT id FROM runs")).all()}

        jobs = db.execute(
            text("SELECT id, type, status, payload, error, created_at, updated_at FROM jobs")
        ).all()
        runs = db.execute(
            text(
                "SELECT id, method, status, params, error, created_at, finished_at, artifact_key, "
                "artifact_sha256, created_by FROM analysis_runs"
            )
        ).all()

        job_missing = [row for row in jobs if row[0] not in existing]
        run_missing = [row for row in runs if row[0] not in existing]
        print(f"jobs {len(jobs)} 条，待补 {len(job_missing)}；analysis_runs {len(runs)} 条，待补 {len(run_missing)}")

        if not args.apply:
            print("干跑结束；加 --apply 才会写库")
            return 0

        for job_id, job_type, status, payload, error, created_at, updated_at in job_missing:
            try:
                params = json.loads(payload or "{}")
            except json.JSONDecodeError:
                params = {}
            name = params.get("name")
            title = JOB_TITLES.get(job_type, job_type)
            db.add(
                Run(
                    id=job_id,
                    kind=job_type,
                    title=f"{title}：{name}" if name else title,
                    status=status,
                    params=params,
                    error=error,
                    started_at=created_at,
                    finished_at=updated_at if status in ("completed", "failed") else None,
                )
            )

        for (run_id, method, status, params, error, created_at, finished_at,
             artifact_key, artifact_sha256, created_by) in run_missing:
            db.add(
                Run(
                    id=run_id,
                    kind=method,
                    title=ANALYSIS_TITLES.get(method, method),
                    status=status,
                    params=params or {},
                    error=error,
                    artifact_key=artifact_key,
                    artifact_sha256=artifact_sha256,
                    created_by=created_by,
                    started_at=created_at,
                    finished_at=finished_at,
                )
            )

        db.commit()
        total = db.execute(text("SELECT count(*) FROM runs")).scalar()
        print(f"回填完成，runs 现有 {total} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
