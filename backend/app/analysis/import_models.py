"""Register a directory of trained scorecards as one `model` ranking source.

The offline models live as `reports/models/expanding-bench20/YYYY-MM.json`. Importing them makes the
simulation read a registered source instead of a path inside the image: the directory becomes a source,
each month becomes a `model_artifacts` row (so a retrain can be skipped when it already exists), and the
day's model is chosen by period.

    python -m app.analysis.import_models --dir reports/models/expanding-bench20 \\
        --source-id bench20-v1 --dataset-version 2 --dataset-sha dfb1524b…
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from app.analysis.artifact import ARTIFACT_ROOT
from app.database import SessionLocal
from app.models.model_artifact import ModelArtifact, fingerprint
from app.models.ranking import RankingSource


def _month_end(period: str) -> str:
    """`2026-09` → `2026-09-30`."""
    import calendar

    year, month = (int(part) for part in period.split("-")[:2])
    return f"{period}-{calendar.monthrange(year, month)[1]:02d}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--display-name", default=None)
    parser.add_argument("--dataset-name", default="scorecard-training-20d-bench")
    parser.add_argument("--dataset-version", type=int, default=None)
    parser.add_argument("--dataset-sha", default=None)
    args = parser.parse_args(argv)

    source_dir = Path(args.dir)
    models = sorted(p for p in source_dir.glob("*.json") if "split" not in p.name and p.name != "index.json")
    if not models:
        print(f"no models in {source_dir}")
        return 1

    target = Path(ARTIFACT_ROOT) / args.source_id / "models"
    target.mkdir(parents=True, exist_ok=True)

    with SessionLocal() as db:
        periods = []
        for path in models:
            payload = json.loads(path.read_text())
            period = payload.get("trained_for_month") or path.stem
            body = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            digest = hashlib.sha256(body.encode()).hexdigest()
            shutil.copyfile(path, target / f"{period}.json")
            periods.append(period)
            dataset = {
                "name": args.dataset_name,
                "version": args.dataset_version,
                "manifest_sha256": args.dataset_sha,
            }
            label = {
                "kind": payload.get("label_kind", "benchmark"),
                "horizon": payload.get("horizon", 20),
            }
            db.merge(
                ModelArtifact(
                    fingerprint=fingerprint(
                        method="scorecard_train",
                        period=period,
                        period_kind="month",
                        params={"bins": payload.get("bins"), "intervals": len(payload.get("factors", []))},
                        factors=payload.get("factors", []),
                        label=label,
                        dataset=dataset,
                    ),
                    method="scorecard_train",
                    period=period,
                    period_kind="month",
                    params={"bins": payload.get("bins")},
                    factors=[{"code": f["code"], "version": 1} for f in payload.get("factors", [])],
                    label=label,
                    dataset_name=dataset["name"],
                    dataset_version=dataset["version"],
                    dataset_sha256=dataset["manifest_sha256"],
                    artifact_key=str(target / f"{period}.json"),
                    artifact_sha256=digest,
                    metrics=payload.get("metrics") or {},
                    status="published",
                    trained_by="import",
                )
            )
        db.merge(
            RankingSource(
                id=args.source_id,
                kind="model",
                display_name=args.display_name or f"{args.source_id}（逐月模型）",
                description=f"{len(periods)} 个月度评分卡，按日期取当期模型在线打分。",
                method="scorecard_train",
                params={"periods": periods},
                artifact_key=str(target),
                artifact_sha256=hashlib.sha256("".join(periods).encode()).hexdigest(),
                # 逐月模型的覆盖区间要写成真实日期，否则界面上的日期选择器显示不出来。
                date_from=f"{min(periods)}-01",
                date_to=_month_end(max(periods)),
                dataset_name=args.dataset_name,
                dataset_version=args.dataset_version,
                dataset_sha256=args.dataset_sha,
                label={"kind": "benchmark", "horizon": 20},
                status="published",
                created_by="import",
            )
        )
        db.commit()
    print(f"{args.source_id}: {len(periods)} models registered ({periods[0]} … {periods[-1]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
