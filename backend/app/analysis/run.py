"""Run one analysis as its own process.

Analyses are not API work: `regime_score` over 2.4 years pulls a few million factor rows and was
OOM-killing the 1 GiB API pod when it ran in a request thread. Running it as a separate process (or a
dedicated worker pod) keeps the API alive and gives the computation its own memory budget.

    python -m app.analysis.run --method regime_score --run-id <id> --params '{"start": "..."}'
"""

from __future__ import annotations

import argparse
import json
import sys

from app.analysis import methods  # noqa: F401  (registration side effect)
from app.database import SessionLocal
from app.services.analysis_service import run_analysis


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--method", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--params", required=True, help="JSON object")
    parser.add_argument("--dataset", default="{}", help="JSON object: {name, version, manifest_sha256}")
    parser.add_argument("--source-id", default=None)
    parser.add_argument("--display-name", default=None)
    parser.add_argument("--created-by", default=None)
    args = parser.parse_args(argv)

    import logging

    from app.services.run_service import CURRENT_RUN

    CURRENT_RUN.set(args.run_id)

    with SessionLocal() as db:
        try:
            run, source = run_analysis(
                db,
                method=args.method,
                params=json.loads(args.params),
                dataset=json.loads(args.dataset),
                source_id=args.source_id,
                display_name=args.display_name,
                created_by=args.created_by,
                run_id=args.run_id,
            )
        except Exception as exc:  # noqa: BLE001 — the run row already carries the error
            print(f"analysis failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        # Read before the session closes: the objects are detached afterwards.
        if hasattr(source, "row_count"):
            summary = f"{run.id} -> {source.id} ({source.row_count:,} rows, {source.artifact_sha256[:12]})"
        else:
            summary = f"{run.id} -> model {source.fingerprint[:12]} for {source.period}"
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
