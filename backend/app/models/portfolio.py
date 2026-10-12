import uuid
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
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# Portfolio config is stored relationally (`portfolio_stocks`, `portfolio_risk_controls`,
# `portfolio_policies`, `portfolio_cash_flows`); the legacy config dict is composed on read.


class Portfolio(Base):
    __tablename__ = "portfolios"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    initial_investment: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(), server_default=func.now(), onupdate=func.now()
    )


class PortfolioStock(Base):
    """One row per portfolio × stock; also holds the watchlist (`status='watching'`).

    ``hold_shares`` / ``avg_cost`` / ``total_cost`` / ``realized_pnl`` / ``last_trade_date`` are
    aggregates over ``portfolio_transactions``. They are maintained by
    ``PortfolioService.record_transaction`` and can be rebuilt with
    ``PortfolioService.rebuild_stock_from_transactions``.
    """

    __tablename__ = "portfolio_stocks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    portfolio_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("portfolios.id", ondelete="CASCADE"), index=True
    )
    ts_code: Mapped[str] = mapped_column(String(16), nullable=False)
    # watching | holding | closed
    status: Mapped[str] = mapped_column(String(16), default="watching")
    hold_shares: Mapped[int] = mapped_column(Integer, default=0)
    avg_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0)
    target_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    target_weight: Mapped[Decimal | None] = mapped_column(Numeric(9, 4), nullable=True)
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    first_buy_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_trade_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    stop_loss_point: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    max_holding_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    atr: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("portfolio_id", "ts_code", name="uq_portfolio_stocks_portfolio_ts_code"),
    )


class PortfolioTransaction(Base):
    """Buy/sell ledger. ``simulation_run_id`` set ⇒ the trade belongs to that backtest run."""

    __tablename__ = "portfolio_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    portfolio_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("portfolios.id", ondelete="CASCADE"), index=True
    )
    simulation_run_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("simulation_runs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    ts_code: Mapped[str] = mapped_column(String(16), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    # buy | sell
    side: Mapped[str] = mapped_column(String(4), nullable=False)
    shares: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    fee: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    tax: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    # realized only on sells (weighted-average cost basis)
    realized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    stop_loss_point: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    reason: Mapped[str] = mapped_column(String(255), default="")
    # manual | simulation | import
    source: Mapped[str] = mapped_column(String(16), default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime(), server_default=func.now())

    __table_args__ = (
        Index("ix_portfolio_transactions_portfolio_date", "portfolio_id", "trade_date"),
        Index("ix_portfolio_transactions_ts_code", "portfolio_id", "ts_code"),
    )


class PortfolioRiskControl(Base):
    """1:1 risk parameters, flattened back into ``config['risk_control']`` for the engine."""

    __tablename__ = "portfolio_risk_controls"

    portfolio_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        primary_key=True,
    )
    bearable_trading_loss: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=0)
    position_control: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=1)
    reserve_profit: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    max_position_size: Mapped[int] = mapped_column(Integer, default=50)
    max_position_ratio: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=0)
    stop_loss_should_check: Mapped[bool] = mapped_column(Boolean, default=True)
    stop_loss_n_times_atr: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=2)
    stop_loss_should_update: Mapped[bool] = mapped_column(Boolean, default=True)
    max_holding_should_check: Mapped[bool] = mapped_column(Boolean, default=True)
    max_holding_days: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(), server_default=func.now(), onupdate=func.now()
    )


class PortfolioPolicy(Base):
    """One backtest policy per row; ``params`` keeps the engine's flattened parameter keys."""

    __tablename__ = "portfolio_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    portfolio_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("portfolios.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(64), default="moving_average")
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(), server_default=func.now(), onupdate=func.now()
    )


class PortfolioCashFlow(Base):
    """Cash in/out of the portfolio (replaces the legacy ``increase_investments`` list)."""

    __tablename__ = "portfolio_cash_flows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    portfolio_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("portfolios.id", ondelete="CASCADE"), index=True
    )
    flow_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    # deposit | withdraw
    kind: Mapped[str] = mapped_column(String(16), default="deposit")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(), server_default=func.now())
