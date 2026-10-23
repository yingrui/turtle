"""store a run's summary metrics on the run row

The ontology mirrors `simulation_runs` as a `Simulation` object, but the numbers a reader wants
(total, return, CAGR, drawdown, win/loss, trade count, window) were computed per request in
`SimulationService.get_summary` and never persisted — so an agent could see *which* runs existed and
nothing about how they did. They are computed once at the end of the run (and backfilled for
existing rows) and stored here.

Revision ID: 005
Revises: 004
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, Sequence[str], None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


COLUMNS = (
    sa.Column("window_start", sa.Date(), nullable=True),
    sa.Column("window_end", sa.Date(), nullable=True),
    sa.Column("initial_total", sa.Numeric(18, 2), nullable=True),
    sa.Column("final_total", sa.Numeric(18, 2), nullable=True),
    # 100-based: 211.60 means "the portfolio is at 211.6% of its start", as the daily log reports.
    sa.Column("return_rate_pct", sa.Numeric(12, 4), nullable=True),
    sa.Column("cagr", sa.Numeric(12, 6), nullable=True),
    sa.Column("years", sa.Integer(), nullable=True),
    sa.Column("max_drawdown_pct", sa.Numeric(12, 4), nullable=True),
    sa.Column("win_count", sa.Integer(), nullable=True),
    sa.Column("loss_count", sa.Integer(), nullable=True),
    sa.Column("holding_count", sa.Integer(), nullable=True),
    sa.Column("trade_count", sa.Integer(), nullable=True),
)


def upgrade() -> None:
    for column in COLUMNS:
        op.add_column("simulation_runs", column)


def downgrade() -> None:
    for column in reversed(COLUMNS):
        op.drop_column("simulation_runs", column.name)
