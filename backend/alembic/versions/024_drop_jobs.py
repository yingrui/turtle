"""删掉 jobs —— 回测、因子计算、选股都改用 runs。

开发阶段直接删；历史已在回填脚本里并入 runs。

Revision ID: 024
Revises: 023
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "024"
down_revision: Union[str, Sequence[str], None] = "023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("jobs")


def downgrade() -> None:
    raise RuntimeError("jobs 已废弃，不提供回滚：历史数据在 runs 里")
