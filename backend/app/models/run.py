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
    #: 逐行日志与一行进度：回测详情页直接展示，回测/因子计算都要用。
    log: Mapped[str] = mapped_column(Text, default="", server_default="")
    progress: Mapped[str] = mapped_column(String(255), default="", server_default="")
    artifact_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    artifact_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # --- 兼容旧字段名 -------------------------------------------------------
    # JobService 的历史代码按 jobs 的字段读写（type / payload / result 是字符串）。
    # 这里给出同名属性，让调用方可以逐步迁移，而不用一次性改几十处。
    @property
    def type(self) -> str:
        return self.kind

    @type.setter
    def type(self, value: str) -> None:
        self.kind = value

    @property
    def payload(self) -> str:
        import json as _json

        return _json.dumps(self.params or {}, ensure_ascii=False)

    @payload.setter
    def payload(self, value: str) -> None:
        import json as _json

        try:
            self.params = _json.loads(value or "{}")
        except _json.JSONDecodeError:
            self.params = {}

    @property
    def result_json(self) -> str | None:
        import json as _json

        return None if not self.result else _json.dumps(self.result, ensure_ascii=False)

    @property
    def created_at(self):
        return self.started_at

    @property
    def updated_at(self):
        return self.finished_at
