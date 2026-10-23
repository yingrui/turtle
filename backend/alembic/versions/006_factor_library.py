"""factor library: definitions and per-stock per-day values

Phase 3 of the roadmap (``docs/research/07-factor-and-stock-selection.md``): a factor's meaning is
one row, its values are a fact table keyed ``(factor_id, ts_code, trade_date)``. Values are a
panel, not objects — the surrogate key would only add a join and get in the way of the daily
upsert that a batch run performs.

Revision ID: 006
Revises: 005
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "006"
down_revision: Union[str, Sequence[str], None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "factor_definitions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("category", sa.String(32), nullable=False, server_default="technical"),
        sa.Column("direction", sa.String(16), nullable=False, server_default="neutral"),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("logic", sa.Text(), nullable=True),
        sa.Column("params", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("lookback_days", sa.SmallInteger(), nullable=True),
        sa.Column("ic_mean", sa.Numeric(10, 6), nullable=True),
        sa.Column("ic_ir", sa.Numeric(10, 6), nullable=True),
        sa.Column("source_ref", sa.String(128), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "factor_values",
        sa.Column(
            "factor_id",
            sa.String(36),
            sa.ForeignKey("factor_definitions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("ts_code", sa.String(16), primary_key=True),
        sa.Column("trade_date", sa.Date(), primary_key=True),
        sa.Column("value", sa.Numeric(20, 6), nullable=False),
        sa.Column("extra", postgresql.JSONB(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_factor_values_factor_date", "factor_values", ["factor_id", "trade_date"])
    op.create_index(
        "ix_factor_values_stock_factor_date",
        "factor_values",
        ["ts_code", "factor_id", "trade_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_factor_values_stock_factor_date", table_name="factor_values")
    op.drop_index("ix_factor_values_factor_date", table_name="factor_values")
    op.drop_table("factor_values")
    op.drop_table("factor_definitions")
