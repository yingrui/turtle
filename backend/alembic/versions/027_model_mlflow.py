"""模型记录 MLflow 身份：哪次实验、哪个 run。

没有这一列时，"这个模型对应 MLflow 的哪次训练"只能靠人记；有了它，界面可以直接跳过去。

Revision ID: 027
Revises: 026
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "027"
down_revision: Union[str, Sequence[str], None] = "026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("model_artifacts", sa.Column("mlflow_run_id", sa.String(64), nullable=True))
    op.add_column("model_artifacts", sa.Column("mlflow_model_version", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("model_artifacts", "mlflow_model_version")
    op.drop_column("model_artifacts", "mlflow_run_id")
