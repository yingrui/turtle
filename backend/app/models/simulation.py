from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    portfolio_name: Mapped[str] = mapped_column(String(128))
    policy_id: Mapped[int] = mapped_column(Integer)
    config_snapshot: Mapped[str] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


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


class SimulationTrade(Base):
    __tablename__ = "simulation_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("simulation_runs.id"), index=True)
    trade_date: Mapped[date] = mapped_column(Date)
    ts_code: Mapped[str] = mapped_column(String(16))
    hold_shares: Mapped[int] = mapped_column(Integer)
    hold_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    buy_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    sell_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    total_cash_return: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    benefit: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    reason: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(32))
