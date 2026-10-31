"""Model artifacts, cached by fingerprint so a run skips training it already has.

Revision ID: 017
Revises: 016
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "017"
down_revision: Union[str, Sequence[str], None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "model_artifacts",
        sa.Column("fingerprint", sa.String(64), primary_key=True),
        sa.Column("method", sa.String(64), nullable=False),
        sa.Column("period", sa.String(16), nullable=False),
        sa.Column("period_kind", sa.String(8), nullable=False),
        sa.Column("params", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("factors", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("label", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("dataset_name", sa.String(128), nullable=True),
        sa.Column("dataset_version", sa.Integer(), nullable=True),
        sa.Column("dataset_sha256", sa.String(64), nullable=True),
        sa.Column("artifact_key", sa.String(512), nullable=False),
        sa.Column("artifact_sha256", sa.String(64), nullable=False),
        sa.Column("metrics", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(16), nullable=False, server_default="published"),
        sa.Column("trained_by", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_model_artifacts_period", "model_artifacts", ["period"])


def downgrade() -> None:
    op.drop_index("ix_model_artifacts_period", table_name="model_artifacts")
    op.drop_table("model_artifacts")
