from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

#: JSONB on PostgreSQL, plain JSON where a sqlite test database builds the same tables.
JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    portfolio_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("portfolios.id", ondelete="SET NULL"), nullable=True, index=True
    )
    portfolio_name: Mapped[str] = mapped_column(String(128))
    policy_id: Mapped[int] = mapped_column(Integer)
    #: Human name for an experiment run (`bench20-top50-2024h2`), so a report can point at it.
    name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: What produced the ranking: `{"ranking": {...}, "dataset": {...}, "label": {...}}`.
    provenance: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, server_default="{}")
    config_snapshot: Mapped[str] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    #: signal = the configured trade policies; model = a scorecard's daily ranking drives the book.
    mode: Mapped[str] = mapped_column(String(16), default="signal", server_default="signal")
    #: fixed = an explicit stock list; dynamic = the model's top-N changes every day.
    pool_mode: Mapped[str] = mapped_column(String(16), default="fixed", server_default="fixed")

    # Summary of the run, computed once when it finishes (`summarize_run`) and backfilled for
    # older rows. The ontology mirrors these onto the `Simulation` object, so a reader does not
    # have to replay the daily log to answer "how did it do?".
    window_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    window_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    initial_total: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    final_total: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    # 100-based: 211.60 means the portfolio ended at 211.6% of its start (the daily log's unit).
    return_rate_pct: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    cagr: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_drawdown_pct: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    win_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    loss_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    holding_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trade_count: Mapped[int | None] = mapped_column(Integer, nullable=True)


class SimulationDaily(Base):
    __tablename__ = "simulation_daily"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("simulation_runs.id"), index=True)
    trade_date: Mapped[date] = mapped_column(Date)
    return_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    benefit: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    investment_total: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    total: Mapped[Decimal] = mapped_column(Numeric(18, 2))


# Per-trade rows live in `simulation_trades` (migration 011): a run's fills belong to the run, not to
# the portfolio's ledger.


class SimulationHolding(Base):
    """What a model-driven run held at the close of one day.

    The live portfolio is not touched by a run: its positions live here, keyed by (run, date, code),
    so "the holdings on 2026-05-14" is a lookup and the run can be re-read years later.
    """

    __tablename__ = "simulation_holdings"

    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("simulation_runs.id", ondelete="CASCADE"), primary_key=True
    )
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    ts_code: Mapped[str] = mapped_column(String(16), primary_key=True)
    shares: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    market_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    weight: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    #: The model's rank and score for that day, when the run is model-driven.
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)

    __table_args__ = (
        Index("ix_simulation_holdings_run_date", "run_id", "trade_date"),
    )


class SimulationTrade(Base):
    """One fill belonging to a run.

    Kept apart from `portfolio_transactions` on purpose: the portfolio's ledger and a backtest's
    ledger are different books, and a nullable `run_id` on one table let every reader pick the wrong
    one by forgetting a filter.
    """

    __tablename__ = "simulation_trades"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("simulation_runs.id", ondelete="CASCADE"), nullable=False
    )
    ts_code: Mapped[str] = mapped_column(String(16), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    side: Mapped[str] = mapped_column(String(4), nullable=False)
    shares: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    fee: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    tax: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    realized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    reason: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(), server_default=func.now())

    __table_args__ = (Index("ix_simulation_trades_run_date", "run_id", "trade_date"),)


class SimulationPool(Base):
    """The set a run was allowed to hold, per day.

    In `fixed` mode it is the configured watchlist (the same rows every day); in `dynamic` mode it is
    that day's top-N with its rank and score. Recorded per day because a dynamic pool has no history
    in today's state.
    """

    __tablename__ = "simulation_pool"

    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("simulation_runs.id", ondelete="CASCADE"), primary_key=True
    )
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    ts_code: Mapped[str] = mapped_column(String(16), primary_key=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    #: Whether the run actually held it that day (a pool member need not be bought).
    held: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    __table_args__ = (Index("ix_simulation_pool_run_date", "run_id", "trade_date"),)
