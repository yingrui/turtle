"""Record what produced a run's ranking: dataset version, label, model.

A run's numbers are only comparable if the reader knows which data, which label and which model
produced them. `name`/`description` are for people; `provenance` is for the report's "复现" section —
machine-written, one JSON object:

    {"ranking": {"source": "model", "policy": "expanding-bench20"},
     "dataset": {"name": "scorecard-training-20d-bench", "version": 1, "manifest_sha256": "…"},
     "label":   {"kind": "benchmark", "horizon": 20, "benchmark": "000300.SH"}}

Revision ID: 015
Revises: 014
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "015"
down_revision: Union[str, Sequence[str], None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "simulation_runs",
        sa.Column("provenance", postgresql.JSONB(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("simulation_runs", "provenance")
