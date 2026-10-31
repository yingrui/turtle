"""The judgement belongs to the run that produced it.

A separate experiment record could be re-run and drift away from the numbers it was based on. A conclusion
stored on the run cannot.

Revision ID: 020
Revises: 019
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "020"
down_revision: Union[str, Sequence[str], None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "simulation_runs",
        sa.Column("verdict", postgresql.JSONB(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("simulation_runs", "verdict")
