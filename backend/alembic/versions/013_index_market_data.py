"""index market data (`index_basic`, `index_daily`) in schema tushare

The external ETL writes these tables; this migration only states the **contract** this app reads, so a
fresh database has them before `/api/data/status` asks for their latest bar. It is deliberately
idempotent: on a database where the ETL already created them, nothing happens.

It also refuses to drop them on downgrade. A migration may describe what it did not create, but it may
not delete data it does not own.

Revision ID: 013
Revises: 012
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "013"
down_revision: Union[str, Sequence[str], None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "tushare"


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name, schema=SCHEMA)


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

    if not _has_table("index_basic"):
        op.create_table(
            "index_basic",
            sa.Column("ts_code", sa.Text(), nullable=False),
            sa.Column("name", sa.Text(), nullable=True),
            sa.Column("fullname", sa.Text(), nullable=True),
            sa.Column("market", sa.Text(), nullable=True),
            sa.Column("publisher", sa.Text(), nullable=True),
            sa.Column("index_type", sa.Text(), nullable=True),
            sa.Column("category", sa.Text(), nullable=True),
            sa.Column("base_date", sa.Date(), nullable=True),
            sa.Column("base_point", sa.Numeric(), nullable=True),
            sa.Column("list_date", sa.Date(), nullable=True),
            sa.Column("weight_rule", sa.Text(), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("exp_date", sa.Date(), nullable=True),
            sa.PrimaryKeyConstraint("ts_code"),
            schema=SCHEMA,
        )

    if not _has_table("index_daily"):
        op.create_table(
            "index_daily",
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
            sa.PrimaryKeyConstraint("ts_code", "trade_date", name="pk_index_daily"),
            schema=SCHEMA,
        )



    # Outside the guard: the table may predate this migration (the ETL owns it) while the index does
    # not. Indexes are a performance contract, not data, so adding one to an existing table is safe.
    op.execute(
        'CREATE INDEX IF NOT EXISTS index_trade_date_on_index_daily '
        f'ON {SCHEMA}.index_daily (trade_date)'
    )


def downgrade() -> None:
    # Intentionally empty: these tables are owned by the external ETL. Dropping them here would delete
    # market data this migration did not create — the contract is additive.
    pass
