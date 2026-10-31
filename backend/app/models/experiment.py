"""An experiment: a question, its variants, its controls, and the verdict.

Today an experiment lives in a run name and a report. That is why the controls were added after the
fact and why "same experiment, new factor" meant rewriting a payload. An experiment is a record: it
expands into a matrix of runs (variants plus controls), and its conclusion is only admissible when the
control cells exist.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    question: Mapped[str] = mapped_column(Text)
    #: `{"kill": "what would falsify this"}` — written before the result is known.
    hypothesis: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, server_default="{}")
    #: `[{"name": "regime", "ranking_source_id": "regime-ma60-v1"}, …]`
    variants: Mapped[list] = mapped_column(JSON_TYPE, default=list, server_default="[]")
    #: `[{"name": "random11", "ranking_source_id": "pool-random-11"}, …]` — required for a verdict.
    controls: Mapped[list] = mapped_column(JSON_TYPE, default=list, server_default="[]")
    label: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, server_default="{}")
    strategy: Mapped[str] = mapped_column(String(32), default="pool_entry")
    window_start: Mapped[str | None] = mapped_column(String(10), nullable=True)
    window_end: Mapped[str | None] = mapped_column(String(10), nullable=True)
    portfolio: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    conclusion: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, server_default="{}")
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ExperimentRun(Base):
    """One cell of the matrix: which variant, and whether it is a control."""

    __tablename__ = "experiment_runs"

    experiment_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("experiments.id", ondelete="CASCADE"), primary_key=True
    )
    variant: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    is_control: Mapped[bool] = mapped_column(default=False)
    job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
