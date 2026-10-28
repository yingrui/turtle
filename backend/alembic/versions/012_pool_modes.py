"""A run's stock pool: fixed or dynamic, and the pool of every day it ran.

`simulation_holdings` answers "what did it hold"; the pool is the larger set a run was *allowed* to
hold — the configured watchlist in `fixed` mode, or the model's top-N that day in `dynamic` mode. It
is recorded per day because a dynamic pool changes daily and the question "what was in the pool on
2026-05-14" has no answer from today's state.

`portfolios.active_run_id` is the pointer that makes a portfolio's pool come from a run instead of
being a hand-edited list.

Revision ID: 012
Revises: 011
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "012"
down_revision: Union[str, Sequence[str], None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    #: fixed = an explicit list (portfolio watchlist / ts_codes); dynamic = the model's top-N each day.
    op.add_column(
        "simulation_runs",
        sa.Column("pool_mode", sa.String(16), nullable=False, server_default="fixed"),
    )
    op.create_table(
        "simulation_pool",
        sa.Column(
            "run_id",
            sa.String(36),
            sa.ForeignKey("simulation_runs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("trade_date", sa.Date(), primary_key=True),
        sa.Column("ts_code", sa.String(16), primary_key=True),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("score", sa.Numeric(18, 6), nullable=True),
        sa.Column("held", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("ix_simulation_pool_run_date", "simulation_pool", ["run_id", "trade_date"])
    op.add_column("portfolios", sa.Column("active_run_id", sa.String(36), nullable=True))


def downgrade() -> None:
    op.drop_column("portfolios", "active_run_id")
    op.drop_index("ix_simulation_pool_run_date", table_name="simulation_pool")
    op.drop_table("simulation_pool")
    op.drop_column("simulation_runs", "pool_mode")
