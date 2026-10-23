"""give a factor definition a formula

A definition without a formula is documentation: the factor exists, nothing computes it. With a
formula it is executable — the engine in ``app/core/factor/engine.py`` evaluates it over the
market-data panel.

Revision ID: 007
Revises: 006
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, Sequence[str], None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("factor_definitions", sa.Column("formula", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("factor_definitions", "formula")
