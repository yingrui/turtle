"""Attach historical simulation runs to an experiment by their name.

The runs that produced experiments 1–3 predate the `experiment_runs` table, so their numbers were never
linked to their definition. This maps them by name prefix, which is what the names were for.

    python -m scripts.backfill_experiment_runs --experiment exp3-regime --prefix exp3- --control-prefix ctrl-
"""

from __future__ import annotations

import argparse

from sqlalchemy import text

from app.database import SessionLocal
from app.services.experiment_service import ExperimentService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--prefix", default=None, help="names starting with this are variants")
    parser.add_argument("--control-prefix", default="ctrl-", help="names starting with this are controls")
    parser.add_argument("--apply", action="store_true", help="without this, only print the plan")
    args = parser.parse_args(argv)

    with SessionLocal() as db:
        rows = db.execute(
            text(
                "SELECT id, name FROM simulation_runs WHERE name IS NOT NULL AND finished_at IS NOT NULL "
                "ORDER BY finished_at"
            )
        ).all()
        service = ExperimentService()
        for run_id, name in rows:
            is_control = args.control_prefix and name.startswith(args.control_prefix)
            if args.prefix and not (name.startswith(args.prefix) or is_control):
                continue
            variant = name.split(":")[-1]
            print(f"{'link' if args.apply else 'would link'} {run_id[:8]} {name} → {args.experiment}/{variant}"
                  f"{' (control)' if is_control else ''}")
            if args.apply:
                service.attach(db, args.experiment, variant, run_id=run_id, is_control=bool(is_control))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
