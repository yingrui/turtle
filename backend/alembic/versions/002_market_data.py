"""market data tables (Tushare sync) in schema tushare

Revision ID: 002
"""

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None

SCHEMA = "tushare"

MARKET_TABLES = (
    "trade_calendar",
    "stock_basic",
    "stock_trade_daily",
    "stock_adj_daily",
    "dividends",
)


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

    op.create_table(
        "trade_calendar",
        sa.Column("exchange", sa.String(10), nullable=True),
        sa.Column("cal_date", sa.Date(), nullable=True),
        sa.Column("is_open", sa.Integer(), nullable=True),
        sa.Column("pretrade_date", sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint("exchange", "cal_date", name="pk_exchange_date"),
        schema=SCHEMA,
    )
    op.create_table(
        "stock_basic",
        sa.Column("ts_code", sa.Text(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("area", sa.Text(), nullable=True),
        sa.Column("industry", sa.Text(), nullable=True),
        sa.Column("fullname", sa.Text(), nullable=True),
        sa.Column("enname", sa.Text(), nullable=True),
        sa.Column("cnspell", sa.Text(), nullable=True),
        sa.Column("market", sa.Text(), nullable=True),
        sa.Column("exchange", sa.Text(), nullable=True),
        sa.Column("curr_type", sa.Text(), nullable=True),
        sa.Column("list_status", sa.Text(), nullable=True),
        sa.Column("list_date", sa.Text(), nullable=True),
        sa.Column("delist_date", sa.Text(), nullable=True),
        sa.Column("is_hs", sa.Text(), nullable=True),
        sa.Column("act_name", sa.Text(), nullable=True),
        sa.Column("act_ent_type", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("ts_code"),
        schema=SCHEMA,
    )
    op.create_table(
        "stock_trade_daily",
        sa.Column("ts_code", sa.Text(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(), nullable=True),
        sa.Column("high", sa.Numeric(), nullable=True),
        sa.Column("low", sa.Numeric(), nullable=True),
        sa.Column("close", sa.Numeric(), nullable=True),
        sa.Column("pre_close", sa.Numeric(), nullable=True),
        sa.Column("change", sa.Numeric(), nullable=True),
        sa.Column("pct_chg", sa.Numeric(), nullable=True),
        sa.Column("vol", sa.Numeric(), nullable=True),
        sa.Column("amount", sa.Numeric(), nullable=True),
        sa.PrimaryKeyConstraint("ts_code", "trade_date", name="pk_code_and_date"),
        schema=SCHEMA,
    )
    op.create_index(
        "index_trade_date_on_stock_trade_daily",
        "stock_trade_daily",
        ["trade_date"],
        schema=SCHEMA,
    )
    op.create_table(
        "stock_adj_daily",
        sa.Column("ts_code", sa.String(10), nullable=True),
        sa.Column("trade_date", sa.Date(), nullable=True),
        sa.Column("adj_factor", sa.Numeric(10, 4), nullable=True),
        sa.PrimaryKeyConstraint("ts_code", "trade_date", name="pk_code_and_date_on_adj_daily"),
        schema=SCHEMA,
    )
    op.create_index(
        "index_trade_date_on_stock_adj_daily",
        "stock_adj_daily",
        ["trade_date"],
        schema=SCHEMA,
    )
    op.create_table(
        "dividends",
        sa.Column("ts_code", sa.String(10), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("ann_date", sa.Date(), nullable=True),
        sa.Column("div_proc", sa.String(24), nullable=True),
        sa.Column("stk_div", sa.Numeric(10, 4), nullable=True),
        sa.Column("stk_bo_rate", sa.Numeric(10, 4), nullable=True),
        sa.Column("stk_co_rate", sa.Numeric(10, 4), nullable=True),
        sa.Column("cash_div", sa.Numeric(10, 4), nullable=True),
        sa.Column("cash_div_tax", sa.Numeric(10, 4), nullable=True),
        sa.Column("record_date", sa.Date(), nullable=True),
        sa.Column("ex_date", sa.Date(), nullable=True),
        sa.Column("pay_date", sa.Date(), nullable=True),
        sa.Column("div_listdate", sa.Date(), nullable=True),
        sa.Column("imp_ann_date", sa.Date(), nullable=True),
        sa.Column("base_date", sa.Date(), nullable=True),
        sa.Column("base_share", sa.Numeric(10, 4), nullable=True),
        sa.Column("update_flag", sa.String(12), nullable=True),
        sa.PrimaryKeyConstraint("ts_code", "ex_date", name="pk_code_and_date_on_dividends"),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("dividends", schema=SCHEMA)
    op.drop_index("index_trade_date_on_stock_adj_daily", table_name="stock_adj_daily", schema=SCHEMA)
    op.drop_table("stock_adj_daily", schema=SCHEMA)
    op.drop_index("index_trade_date_on_stock_trade_daily", table_name="stock_trade_daily", schema=SCHEMA)
    op.drop_table("stock_trade_daily", schema=SCHEMA)
    op.drop_table("stock_basic", schema=SCHEMA)
    op.drop_table("trade_calendar", schema=SCHEMA)
    op.execute(f"DROP SCHEMA IF EXISTS {SCHEMA}")
