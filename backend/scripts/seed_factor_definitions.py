"""Load the factor library into ``factor_definitions``.

The catalogue is the openKMS `AlphaFactor` library (44 distinct factors; the knowledge base holds
the prose, this table holds what the system can compute) plus the three baseline factors the
roadmap asks for. Upserts by ``code``, so re-running after editing the JSON is safe.

    python -m scripts.seed_factor_definitions [--dry-run]

A factor without a ``formula`` is documentation: the inputs it needs (financial statements, order
flow, northbound holdings) are not in this database.
"""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

from sqlalchemy import select

from app.database import SessionLocal
from app.models import FactorDefinition

DATA = Path(__file__).parent / "data" / "factor_definitions.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    catalogue = json.loads(DATA.read_text())
    db = SessionLocal()
    try:
        created = updated = 0
        for entry in catalogue:
            existing = db.scalar(
                select(FactorDefinition).where(FactorDefinition.code == entry["code"])
            )
            if existing:
                for field, value in entry.items():
                    setattr(existing, field, value)
                updated += 1
            else:
                db.add(FactorDefinition(id=str(uuid.uuid4()), **entry))
                created += 1
        computable = sum(1 for e in catalogue if e.get("formula"))
        print(f"{len(catalogue)} definitions: {created} created, {updated} updated, {computable} computable")
        if args.dry_run:
            db.rollback()
        else:
            db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
