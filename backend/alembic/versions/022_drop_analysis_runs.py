"""删掉 analysis_runs —— 分析执行统一记在 runs。

开发阶段直接删；历史数据已在 021 之后用 scripts/backfill_runs.py 回填进 runs。

Revision ID: 022
Revises: 021
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "022"
down_revision: Union[str, Sequence[str], None] = "021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("analysis_runs")


def downgrade() -> None:
    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("method", sa.String(64), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("dataset_name", sa.String(128), nullable=True),
        sa.Column("dataset_version", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("progress", sa.String(255), nullable=False),
        sa.Column("artifact_key", sa.String(512), nullable=True),
        sa.Column("artifact_sha256", sa.String(64), nullable=True),
        sa.Column("source_id", sa.String(64), nullable=True),
        sa.Column("code_revision", sa.String(64), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
    )
