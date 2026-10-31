"""Factor and label definitions as objects, so nothing is an undeclared string.

`(code, version)` of a factor goes into the model fingerprint, so a formula change invalidates cached
models instead of silently reusing one trained on different inputs. A label is an object because the
same "bench20" appeared in four places — export, training, dataset naming, report text — and nothing
checked that they agreed.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")


class FactorSpec(Base):
    __tablename__ = "factor_specs"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    formula: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Tables/columns the factor reads, and how they are joined point-in-time, e.g.
    #: `[{"table": "income", "column": "n_income", "as_of": "ann_date"}]`.
    needs: Mapped[list] = mapped_column(JSON_TYPE, default=list, server_default="[]")
    pit: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, server_default="{}")
    universe: Mapped[str] = mapped_column(String(32), default="all_a")
    direction: Mapped[int] = mapped_column(Integer, default=1)
    category: Mapped[str] = mapped_column(String(32), default="price")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Label(Base):
    """A prediction target: what "success" means, and when it is realised."""

    __tablename__ = "labels"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    kind: Mapped[str] = mapped_column(String(24))          # benchmark | relative | absolute | triple_barrier
    horizon: Mapped[int] = mapped_column(Integer, default=20)
    benchmark: Mapped[str | None] = mapped_column(String(16), nullable=True)
    #: Defaults are Python-side: a label must always state how it enters and exits, and the two
    #: strings are what a report quotes.
    entry: Mapped[str] = mapped_column(String(32), default="open[t+1]", server_default="open[t+1]")
    exit: Mapped[str] = mapped_column(String(48), default="close[t+1+h]", server_default="close[t+1+h]")
    filters: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, server_default="{}")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def as_provenance(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "horizon": self.horizon,
            "benchmark": self.benchmark,
        }
