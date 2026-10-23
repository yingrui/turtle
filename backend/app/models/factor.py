"""Factor library: what a factor means, and its value per stock per day.

Two tables, split by grain:

- ``factor_definitions`` — one row per factor: code, meaning, direction, where it comes from.
- ``factor_values`` — the panel: ``(factor_id, ts_code, trade_date) → value``. A fact table, so it
  carries a natural composite key instead of a surrogate id; that makes an ETL/backfill an
  ``ON CONFLICT DO UPDATE`` and a cross-section a single index scan.

Market data is read-only (`tushare.*`); computed factors live here in `public`.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

#: JSONB on PostgreSQL (indexable, the real schema) but plain JSON elsewhere, so the sqlite test
#: suite can create the same tables.
JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")


class FactorDefinition(Base):
    """A factor's identity and meaning. ``code`` is the stable name code refers to."""

    __tablename__ = "factor_definitions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    #: Stable identifier — `mom_20d`, `EP_TTM`. Code and selection rules reference this.
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    #: fundamental | price-volume | technical | sentiment
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="technical")
    #: positive (higher is better) | negative (lower is better) | neutral
    direction: Mapped[str] = mapped_column(String(16), nullable=False, default="neutral")
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    #: How it is computed, in words or pseudo-code.
    logic: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Parameters of a parameterised family (`window`, `n_times_atr`, …).
    params: Mapped[dict] = mapped_column(
        JSON_TYPE, nullable=False, default=dict, server_default="{}"
    )
    #: Longest lookback the factor needs, so a batch knows how much history to load.
    lookback_days: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    #: Research statistics, filled when someone measures them; '-' / null means unmeasured.
    ic_mean: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    ic_ir: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    #: Provenance: handbook, paper, or the module that computes it.
    source_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(), server_default=func.now(), onupdate=func.now()
    )

    values: Mapped[list["FactorValue"]] = relationship(
        back_populates="factor", cascade="all, delete-orphan"
    )


class FactorValue(Base):
    """One factor's value for one stock on one day.

    Keyed naturally: re-running a calculation for the same day overwrites in place, and neither
    the cross-section (`factor_date`) nor the panel (`stock_date`) needs a join to a surrogate.
    """

    __tablename__ = "factor_values"

    factor_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("factor_definitions.id", ondelete="CASCADE"), primary_key=True
    )
    ts_code: Mapped[str] = mapped_column(String(16), primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    #: Non-null when a factor emits several numbers per day (a score plus a rank, …).
    extra: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(), server_default=func.now(), onupdate=func.now()
    )

    factor: Mapped[FactorDefinition] = relationship(back_populates="values")

    __table_args__ = (
        # Cross-section: one day of one factor across every stock.
        Index("ix_factor_values_factor_date", "factor_id", "trade_date"),
        # Panel: one stock's history for a factor (the PK's factor_id prefix does not help here).
        Index("ix_factor_values_stock_factor_date", "ts_code", "factor_id", "trade_date"),
    )
