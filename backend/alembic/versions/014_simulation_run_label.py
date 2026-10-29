"""A name and a description for a simulation run.

A run's id is a uuid, so an experiment report saying "run 3094764d" is hard to find and impossible to
remember. A name (`bench20-top50-2024h2`) and a short description make the report and the run the same
thing, which is what an experiment is.

Revision ID: 014
Revises: 013
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "014"
down_revision: Union[str, Sequence[str], None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("simulation_runs", sa.Column("name", sa.String(128), nullable=True))
    op.add_column("simulation_runs", sa.Column("description", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("simulation_runs", "description")
    op.drop_column("simulation_runs", "name")
