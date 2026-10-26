"""Portfolio lifecycle: membership intervals and an append-only event log.

`status` gains `dropped` (removed from the portfolio — a soft delete; the row stays). Membership is
recorded as an interval (`joined_at` → `left_at`) so "which stocks were in the portfolio on day X" is
a range query, not a replay. The event log records *why* (rank, score, rule, model version) and its
unique key is the daily job's idempotency key.

Revision ID: 009
Revises: 008
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: Union[str, Sequence[str], None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("portfolio_stocks", sa.Column("joined_at", sa.Date(), nullable=True))
    op.add_column("portfolio_stocks", sa.Column("left_at", sa.Date(), nullable=True))
    op.add_column(
        "portfolio_stocks",
        sa.Column("episode", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column("portfolio_stocks", sa.Column("dropped_at", sa.DateTime(), nullable=True))
    op.add_column("portfolio_stocks", sa.Column("last_seen_in_pool", sa.Date(), nullable=True))

    op.create_table(
        "portfolio_stock_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "portfolio_id",
            sa.String(36),
            sa.ForeignKey("portfolios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ts_code", sa.String(16), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("event", sa.String(24), nullable=False),
        sa.Column("from_status", sa.String(16), nullable=True),
        sa.Column("to_status", sa.String(16), nullable=True),
        sa.Column("episode", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("score", sa.Numeric(18, 6), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("rule", sa.String(64), nullable=True),
        sa.Column("rule_params", sa.JSON(), nullable=True),
        sa.Column("model_name", sa.String(128), nullable=True),
        sa.Column("model_version", sa.Integer(), nullable=True),
        sa.Column("dataset_version", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(16), nullable=False, server_default="simulation"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "portfolio_id", "trade_date", "ts_code", "event", name="uq_portfolio_stock_event"
        ),
    )
    op.create_index(
        "ix_portfolio_stock_events_portfolio_date",
        "portfolio_stock_events",
        ["portfolio_id", "trade_date"],
    )
    # Existing rows predate the lifecycle: treat "now" as their join date so a membership query on a
    # past date honestly returns nothing rather than inventing history.
    op.execute(
        "UPDATE portfolio_stocks SET joined_at = COALESCE(first_buy_date, created_at::date), "
        "left_at = CASE WHEN status = 'closed' THEN last_trade_date ELSE NULL END"
    )


def downgrade() -> None:
    op.drop_index("ix_portfolio_stock_events_portfolio_date", table_name="portfolio_stock_events")
    op.drop_table("portfolio_stock_events")
    for column in ("last_seen_in_pool", "dropped_at", "episode", "left_at", "joined_at"):
        op.drop_column("portfolio_stocks", column)
