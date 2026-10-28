"""A run's fills move out of the portfolio ledger into `simulation_trades`.

`portfolio_transactions.simulation_run_id` made one table hold two books: the portfolio's own trades
and every backtest's fills. Nothing in the schema said which was which, so the portfolio's trade page
listed backtests and `rebuild_stock_from_transactions` would happily replay a backtest into a live
position. A tag every query has to remember is not a boundary.

A run's fills now belong to the run: `simulation_trades(run_id, …)`, next to `simulation_daily` and
`simulation_holdings`. `portfolio_transactions` is the portfolio's own ledger again.

Revision ID: 011
Revises: 010
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "011"
down_revision: Union[str, Sequence[str], None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "simulation_trades",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(36),
            sa.ForeignKey("simulation_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ts_code", sa.String(16), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("side", sa.String(4), nullable=False),
        sa.Column("shares", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(18, 4), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), default=0),
        sa.Column("fee", sa.Numeric(18, 2), default=0),
        sa.Column("tax", sa.Numeric(18, 2), default=0),
        sa.Column("realized_pnl", sa.Numeric(18, 2), nullable=True),
        sa.Column("reason", sa.String(255), default=""),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_simulation_trades_run_date", "simulation_trades", ["run_id", "trade_date"])

    # Existing run fills move across; the ids are kept so anything that referenced one still resolves.
    op.execute(
        """
        INSERT INTO simulation_trades
            (id, run_id, ts_code, trade_date, side, shares, price, amount, fee, tax, realized_pnl,
             reason, created_at)
        SELECT id, simulation_run_id, ts_code, trade_date, side, shares, price, amount, fee, tax,
               realized_pnl, reason, created_at
        FROM portfolio_transactions
        WHERE simulation_run_id IS NOT NULL
        """
    )
    op.execute("DELETE FROM portfolio_transactions WHERE simulation_run_id IS NOT NULL")
    op.drop_index("ix_portfolio_transactions_simulation_run_id", table_name="portfolio_transactions")
    op.drop_constraint(
        "portfolio_transactions_simulation_run_id_fkey",
        "portfolio_transactions",
        type_="foreignkey",
    )
    op.drop_column("portfolio_transactions", "simulation_run_id")


def downgrade() -> None:
    op.add_column(
        "portfolio_transactions", sa.Column("simulation_run_id", sa.String(36), nullable=True)
    )
    op.create_foreign_key(
        "portfolio_transactions_simulation_run_id_fkey",
        "portfolio_transactions",
        "simulation_runs",
        ["simulation_run_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_portfolio_transactions_simulation_run_id",
        "portfolio_transactions",
        ["simulation_run_id"],
    )
    op.execute(
        """
        UPDATE portfolio_transactions t
        SET simulation_run_id = s.run_id
        FROM simulation_trades s
        WHERE t.id = s.id
        """
    )
    op.drop_index("ix_simulation_trades_run_date", table_name="simulation_trades")
    op.drop_table("simulation_trades")
