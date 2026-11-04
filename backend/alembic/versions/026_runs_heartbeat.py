"""runs 加心跳时间：判断"还在跑"还是"线程已死"。

后台线程随进程一起消失时，记录会一直停在 running。有心跳就能靠"多久没更新"判定失效。

Revision ID: 026
Revises: 025
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "026"
down_revision: Union[str, Sequence[str], None] = "025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("heartbeat_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("runs", "heartbeat_at")
