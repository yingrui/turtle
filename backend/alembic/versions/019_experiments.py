"""Experiments hold their variants, their controls and their verdict.

Revision ID: 019
Revises: 018
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "019"
down_revision: Union[str, Sequence[str], None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "experiments",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("hypothesis", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("variants", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("controls", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("label", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("strategy", sa.String(32), nullable=False, server_default="pool_entry"),
        sa.Column("window_start", sa.String(10), nullable=True),
        sa.Column("window_end", sa.String(10), nullable=True),
        sa.Column("portfolio", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("conclusion", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_by", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "experiment_runs",
        sa.Column("experiment_id", sa.String(64), sa.ForeignKey("experiments.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("variant", sa.String(64), primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=True),
        sa.Column("is_control", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("job_id", sa.String(36), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("experiment_runs")
    op.drop_table("experiments")
