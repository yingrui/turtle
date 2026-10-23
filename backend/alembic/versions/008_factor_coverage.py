"""store factor coverage on the definition

The catalogue answered "how many values has this factor produced, over how many stocks, between
which dates?" by aggregating `factor_values` on every page view — a `count(distinct ts_code)` over
millions of rows, which made the list take seconds. Coverage is a property of the last compute run,
so it is written then and read as a column.

Revision ID: 008
Revises: 007
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: Union[str, Sequence[str], None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("factor_definitions", sa.Column("value_count", sa.BigInteger(), nullable=False, server_default="0"))
    op.add_column("factor_definitions", sa.Column("stock_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("factor_definitions", sa.Column("first_date", sa.Date(), nullable=True))
    op.add_column("factor_definitions", sa.Column("last_date", sa.Date(), nullable=True))
    op.add_column("factor_definitions", sa.Column("computed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    for column in ("computed_at", "last_date", "first_date", "stock_count", "value_count"):
        op.drop_column("factor_definitions", column)
