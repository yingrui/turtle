"""initial schema

Revision ID: 001
"""

from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("login", sa.String(64), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("progress", sa.String(255), nullable=False, server_default=""),
        sa.Column("payload", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("log", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "simulation_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), nullable=True),
        sa.Column("portfolio_name", sa.String(128), nullable=False),
        sa.Column("policy_id", sa.Integer(), nullable=False),
        sa.Column("config_snapshot", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "simulation_daily",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("simulation_runs.id"), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("return_rate", sa.Numeric(18, 6), nullable=False),
        sa.Column("balance", sa.Numeric(18, 2), nullable=False),
        sa.Column("benefit", sa.Numeric(18, 2), nullable=False),
        sa.Column("investment_total", sa.Numeric(18, 2), nullable=False),
        sa.Column("total", sa.Numeric(18, 2), nullable=False),
    )
    op.create_table(
        "simulation_trades",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("simulation_runs.id"), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("ts_code", sa.String(16), nullable=False),
        sa.Column("hold_shares", sa.Integer(), nullable=False),
        sa.Column("hold_date", sa.Date(), nullable=True),
        sa.Column("buy_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("sell_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("total_cash_return", sa.Numeric(18, 2), nullable=True),
        sa.Column("benefit", sa.Numeric(18, 2), nullable=True),
        sa.Column("reason", sa.String(255), nullable=False, server_default=""),
        sa.Column("status", sa.String(32), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("simulation_trades")
    op.drop_table("simulation_daily")
    op.drop_table("simulation_runs")
    op.drop_table("jobs")
    op.drop_table("users")
