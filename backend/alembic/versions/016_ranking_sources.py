"""Analyses produce artifacts; artifacts become ranking sources.

Simulations used to take a file path in the job payload. That is how a provenance field ended up
pointing at a dataset version whose objects no longer existed. A run now references `ranking_sources.id`
and records the artifact's sha256.

Revision ID: 016
Revises: 015
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "016"
down_revision: Union[str, Sequence[str], None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("method", sa.String(64), nullable=False),
        sa.Column("params", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("dataset_name", sa.String(128), nullable=True),
        sa.Column("dataset_version", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("progress", sa.String(255), nullable=False, server_default=""),
        sa.Column("artifact_key", sa.String(512), nullable=True),
        sa.Column("artifact_sha256", sa.String(64), nullable=True),
        sa.Column("source_id", sa.String(64), nullable=True),
        sa.Column("code_revision", sa.String(64), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_analysis_runs_method", "analysis_runs", ["method"])

    op.create_table(
        "ranking_sources",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("method", sa.String(64), nullable=True),
        sa.Column("params", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("artifact_key", sa.String(512), nullable=False),
        sa.Column("artifact_sha256", sa.String(64), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("date_from", sa.String(10), nullable=True),
        sa.Column("date_to", sa.String(10), nullable=True),
        sa.Column("universe_size", sa.Integer(), nullable=True),
        sa.Column("dataset_name", sa.String(128), nullable=True),
        sa.Column("dataset_version", sa.Integer(), nullable=True),
        sa.Column("dataset_sha256", sa.String(64), nullable=True),
        sa.Column("label", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(16), nullable=False, server_default="published"),
        sa.Column("validation", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("analysis_run_id", sa.String(36), nullable=True),
        sa.Column("created_by", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("deprecated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_ranking_sources_status", "ranking_sources", ["status"])

    op.add_column("simulation_runs", sa.Column("ranking_source_id", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("simulation_runs", "ranking_source_id")
    op.drop_index("ix_ranking_sources_status", table_name="ranking_sources")
    op.drop_table("ranking_sources")
    op.drop_index("ix_analysis_runs_method", table_name="analysis_runs")
    op.drop_table("analysis_runs")
