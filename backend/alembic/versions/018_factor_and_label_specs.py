"""Factors and labels become declared objects.

Revision ID: 018
Revises: 017
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "018"
down_revision: Union[str, Sequence[str], None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "factor_specs",
        sa.Column("code", sa.String(64), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("formula", sa.Text(), nullable=True),
        sa.Column("needs", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("pit", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("universe", sa.String(32), nullable=False, server_default="all_a"),
        sa.Column("direction", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("category", sa.String(32), nullable=False, server_default="price"),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "labels",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("horizon", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("benchmark", sa.String(16), nullable=True),
        sa.Column("entry", sa.String(32), nullable=False, server_default="open[t+1]"),
        sa.Column("exit", sa.String(48), nullable=False, server_default="close[t+1+h]"),
        sa.Column("filters", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("labels")
    op.drop_table("factor_specs")
