"""统一的一次后台执行。

回测、因子计算、评分模型、导出训练集 —— 系统眼里都是"跑了个东西"：有状态、有结果、会失败、会因重启中断。
这里只记录**执行**；执行产生的业务结果（回测的成交与净值）仍在各自的表里，两者不混。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str | None] = mapped_column(String(160), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    params: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, server_default="{}")
    result: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, server_default="{}")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifact_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    artifact_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
