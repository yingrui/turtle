"""Analyses, their runs, and the ranking sources they publish.

The offline scripts became things the product can run and reference. An **analysis run** is history:
it pins the parameters, the dataset version and the code revision, and produces a content-addressed
**artifact**. A **ranking source** is that artifact once it is validated — the only thing a simulation
may rank by, so a run's provenance is `{source_id, artifact_sha256}` instead of a file path.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")


class RankingSource(Base):
    """A validated artifact that simulations may rank by. Immutable once published."""

    __tablename__ = "ranking_sources"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(24))          # score_table | model | factor_combo
    display_name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    method: Mapped[str | None] = mapped_column(String(64), nullable=True)
    params: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, server_default="{}")
    artifact_key: Mapped[str] = mapped_column(String(512))
    artifact_sha256: Mapped[str] = mapped_column(String(64))
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    date_from: Mapped[str | None] = mapped_column(String(10), nullable=True)
    date_to: Mapped[str | None] = mapped_column(String(10), nullable=True)
    universe_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dataset_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dataset_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dataset_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    label: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, server_default="{}")
    status: Mapped[str] = mapped_column(String(16), default="published")
    validation: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, server_default="{}")
    analysis_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    deprecated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
