"""删掉 experiments / experiment_runs。

结论挂在回测上是最终形态（simulation_runs.verdict）,"实验"这一层是过渡产物，已从菜单移除，现连同数据一起删除。

Revision ID: 025
Revises: 024
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "025"
down_revision: Union[str, Sequence[str], None] = "024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("experiment_runs")
    op.drop_table("experiments")


def downgrade() -> None:
    raise RuntimeError("experiments 已废弃，不提供回滚")
