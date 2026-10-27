"""Daily holdings inside a simulation run, and the run's mode.

A run that is driven by a model updates its holdings every day, and "what did it hold on day X" is a
question about the run, not about the live portfolio. Recording the positions per day makes that a
lookup instead of a replay, and keeps the run's own state out of `portfolio_stocks`.

Revision ID: 010
Revises: 009
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: Union[str, Sequence[str], None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "simulation_runs",
        sa.Column("mode", sa.String(16), nullable=False, server_default="signal"),
    )
    op.create_table(
        "simulation_holdings",
        sa.Column(
            "run_id",
            sa.String(36),
            sa.ForeignKey("simulation_runs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("trade_date", sa.Date(), primary_key=True),
        sa.Column("ts_code", sa.String(16), primary_key=True),
        sa.Column("shares", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(18, 4), nullable=False),
        sa.Column("market_value", sa.Numeric(18, 2), nullable=False),
        sa.Column("weight", sa.Numeric(9, 6), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("score", sa.Numeric(18, 6), nullable=True),
    )
    op.create_index(
        "ix_simulation_holdings_run_date", "simulation_holdings", ["run_id", "trade_date"]
    )


def downgrade() -> None:
    op.drop_index("ix_simulation_holdings_run_date", table_name="simulation_holdings")
    op.drop_table("simulation_holdings")
    op.drop_column("simulation_runs", "mode")
