"""给 runs 加日志与进度列：回测/因子计算要显示逐行日志。

先加列并开始双写，读路径下一轮再切 —— 这一轮不让任何一条路断掉。

Revision ID: 023
Revises: 022
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "023"
down_revision: Union[str, Sequence[str], None] = "022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("log", sa.Text(), nullable=False, server_default=""))
    op.add_column("runs", sa.Column("progress", sa.String(255), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("runs", "progress")
    op.drop_column("runs", "log")
