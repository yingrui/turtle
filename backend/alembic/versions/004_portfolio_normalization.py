"""normalize portfolio holdings and trades into relational tables

Replaces ``portfolios.config`` (JSON) with ``portfolio_stocks``,
``portfolio_transactions``, ``portfolio_risk_controls``, ``portfolio_policies`` and
``portfolio_cash_flows``; retires ``simulation_trades`` in favour of
``portfolio_transactions.simulation_run_id``.

Data migration is best-effort: legacy ``config`` values are copied before the column is
dropped, and the ``downgrade`` rebuilds a lossy config (daily holding snapshots were never
stored relationally).

Revision ID: 004
Revises: 003
"""

import json
import uuid
from datetime import date

from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def _as_dict(value) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        return json.loads(value)
    return {}


def _as_date(value) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _num(value, default=None):
    if value is None or value == "":
        return default
    return value


# ---------------------------------------------------------------- upgrade

def upgrade() -> None:
    op.create_table(
        "portfolio_stocks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("portfolio_id", sa.String(36), sa.ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ts_code", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), server_default="watching"),
        sa.Column("hold_shares", sa.Integer(), server_default="0"),
        sa.Column("avg_cost", sa.Numeric(18, 4), server_default="0"),
        sa.Column("total_cost", sa.Numeric(18, 4), server_default="0"),
        sa.Column("target_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("target_weight", sa.Numeric(9, 4), nullable=True),
        sa.Column("realized_pnl", sa.Numeric(18, 2), server_default="0"),
        sa.Column("first_buy_date", sa.Date(), nullable=True),
        sa.Column("last_trade_date", sa.Date(), nullable=True),
        sa.Column("stop_loss_point", sa.Numeric(18, 4), nullable=True),
        sa.Column("max_holding_days", sa.Integer(), nullable=True),
        sa.Column("atr", sa.Numeric(18, 4), nullable=True),
        sa.Column("note", sa.Text(), server_default=""),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("portfolio_id", "ts_code", name="uq_portfolio_stocks_portfolio_ts_code"),
        if_not_exists=True,
    )
    op.create_index("ix_portfolio_stocks_portfolio_id", "portfolio_stocks", ["portfolio_id"], if_not_exists=True)

    op.create_table(
        "portfolio_transactions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("portfolio_id", sa.String(36), sa.ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "simulation_run_id",
            sa.String(36),
            sa.ForeignKey("simulation_runs.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("ts_code", sa.String(16), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("side", sa.String(4), nullable=False),
        sa.Column("shares", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(18, 4), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), server_default="0"),
        sa.Column("fee", sa.Numeric(18, 2), server_default="0"),
        sa.Column("tax", sa.Numeric(18, 2), server_default="0"),
        sa.Column("realized_pnl", sa.Numeric(18, 2), nullable=True),
        sa.Column("stop_loss_point", sa.Numeric(18, 4), nullable=True),
        sa.Column("reason", sa.String(255), server_default=""),
        sa.Column("source", sa.String(16), server_default="manual"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        if_not_exists=True,
    )
    op.create_index("ix_portfolio_transactions_portfolio_id", "portfolio_transactions", ["portfolio_id"], if_not_exists=True)
    op.create_index("ix_portfolio_transactions_simulation_run_id", "portfolio_transactions", ["simulation_run_id"], if_not_exists=True)
    op.create_index("ix_portfolio_transactions_portfolio_date", "portfolio_transactions", ["portfolio_id", "trade_date"], if_not_exists=True)
    op.create_index("ix_portfolio_transactions_ts_code", "portfolio_transactions", ["portfolio_id", "ts_code"], if_not_exists=True)

    op.create_table(
        "portfolio_risk_controls",
        sa.Column("portfolio_id", sa.String(36), sa.ForeignKey("portfolios.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("bearable_trading_loss", sa.Numeric(9, 4), server_default="0"),
        sa.Column("position_control", sa.Numeric(9, 4), server_default="1"),
        sa.Column("reserve_profit", sa.Numeric(18, 2), server_default="0"),
        sa.Column("max_position_size", sa.Integer(), server_default="50"),
        sa.Column("max_position_ratio", sa.Numeric(9, 4), server_default="0"),
        sa.Column("stop_loss_should_check", sa.Boolean(), server_default=sa.true()),
        sa.Column("stop_loss_n_times_atr", sa.Numeric(9, 4), server_default="2"),
        sa.Column("stop_loss_should_update", sa.Boolean(), server_default=sa.true()),
        sa.Column("max_holding_should_check", sa.Boolean(), server_default=sa.true()),
        sa.Column("max_holding_days", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        if_not_exists=True,
    )

    op.create_table(
        "portfolio_policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("portfolio_id", sa.String(36), sa.ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(64), server_default="moving_average"),
        sa.Column("params", sa.JSON(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        if_not_exists=True,
    )
    op.create_index("ix_portfolio_policies_portfolio_id", "portfolio_policies", ["portfolio_id"], if_not_exists=True)

    op.create_table(
        "portfolio_cash_flows",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("portfolio_id", sa.String(36), sa.ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("flow_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("kind", sa.String(16), server_default="deposit"),
        sa.Column("note", sa.Text(), server_default=""),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        if_not_exists=True,
    )
    op.create_index("ix_portfolio_cash_flows_portfolio_id", "portfolio_cash_flows", ["portfolio_id"], if_not_exists=True)

    op.add_column("portfolios", sa.Column("start_date", sa.Date(), nullable=True))
    op.add_column("portfolios", sa.Column("initial_investment", sa.Numeric(18, 2), server_default="0"))
    op.add_column("portfolios", sa.Column("balance", sa.Numeric(18, 2), server_default="0"))
    op.add_column("simulation_runs", sa.Column("portfolio_id", sa.String(36), nullable=True))
    op.create_foreign_key(
        "fk_simulation_runs_portfolio_id",
        "simulation_runs",
        "portfolios",
        ["portfolio_id"],
        ["id"],
        ondelete="SET NULL",
    )

    _backfill_from_config()
    _backfill_simulation_trades()

    op.drop_table("simulation_trades")
    op.drop_column("portfolios", "config")


def _backfill_from_config() -> None:
    conn = op.get_bind()
    portfolios = sa.table(
        "portfolios",
        sa.column("id", sa.String),
        sa.column("name", sa.String),
        sa.column("config", sa.JSON),
        sa.column("start_date", sa.Date),
        sa.column("initial_investment", sa.Numeric),
        sa.column("balance", sa.Numeric),
    )
    stocks = sa.table(
        "portfolio_stocks",
        sa.column("id", sa.String),
        sa.column("portfolio_id", sa.String),
        sa.column("ts_code", sa.String),
        sa.column("status", sa.String),
        sa.column("hold_shares", sa.Integer),
        sa.column("avg_cost", sa.Numeric),
        sa.column("total_cost", sa.Numeric),
        sa.column("first_buy_date", sa.Date),
        sa.column("last_trade_date", sa.Date),
        sa.column("stop_loss_point", sa.Numeric),
    )
    transactions = sa.table(
        "portfolio_transactions",
        sa.column("id", sa.String),
        sa.column("portfolio_id", sa.String),
        sa.column("ts_code", sa.String),
        sa.column("trade_date", sa.Date),
        sa.column("side", sa.String),
        sa.column("shares", sa.Integer),
        sa.column("price", sa.Numeric),
        sa.column("amount", sa.Numeric),
        sa.column("stop_loss_point", sa.Numeric),
        sa.column("reason", sa.String),
        sa.column("source", sa.String),
    )
    risk = sa.table(
        "portfolio_risk_controls",
        sa.column("portfolio_id", sa.String),
        sa.column("bearable_trading_loss", sa.Numeric),
        sa.column("position_control", sa.Numeric),
        sa.column("reserve_profit", sa.Numeric),
        sa.column("max_position_size", sa.Integer),
        sa.column("max_position_ratio", sa.Numeric),
        sa.column("stop_loss_should_check", sa.Boolean),
        sa.column("stop_loss_n_times_atr", sa.Numeric),
        sa.column("stop_loss_should_update", sa.Boolean),
        sa.column("max_holding_should_check", sa.Boolean),
        sa.column("max_holding_days", sa.Integer),
    )
    policies = sa.table(
        "portfolio_policies",
        sa.column("id", sa.String),
        sa.column("portfolio_id", sa.String),
        sa.column("name", sa.String),
        sa.column("params", sa.JSON),
        sa.column("sort_order", sa.Integer),
    )
    flows = sa.table(
        "portfolio_cash_flows",
        sa.column("id", sa.String),
        sa.column("portfolio_id", sa.String),
        sa.column("flow_date", sa.Date),
        sa.column("amount", sa.Numeric),
        sa.column("kind", sa.String),
        sa.column("note", sa.Text),
    )

    for row in conn.execute(sa.select(portfolios)).mappings():
        config = _as_dict(row["config"])
        start_date = _as_date(config.get("start_date"))
        initial = _num(config.get("initial_investment"), 0)
        balance = _num(config.get("balance"), 0)
        conn.execute(
            portfolios.update()
            .where(portfolios.c.id == row["id"])
            .values(start_date=start_date, initial_investment=initial, balance=balance)
        )

        seen: set[str] = set()
        for ts_code in config.get("follow_stocks") or []:
            code = str(ts_code).strip().upper()
            if not code or code in seen:
                continue
            seen.add(code)
            conn.execute(stocks.insert().values(id=str(uuid.uuid4()), portfolio_id=row["id"], ts_code=code, status="watching"))

        for inv in config.get("investments") or []:
            code = str(inv.get("ts_code") or "").strip().upper()
            if not code:
                continue
            shares = int(inv.get("hold_shares") or 0)
            price = _num(inv.get("buy_price"), 0)
            total = float(shares) * float(price)
            values = {
                "hold_shares": shares,
                "avg_cost": price,
                "total_cost": total,
                "stop_loss_point": _num(inv.get("stop_loss_point")),
                "first_buy_date": start_date,
                "last_trade_date": start_date,
                "status": "holding" if shares else "watching",
            }
            if code in seen:
                conn.execute(stocks.update().where(sa.and_(stocks.c.portfolio_id == row["id"], stocks.c.ts_code == code)).values(**values))
            else:
                seen.add(code)
                conn.execute(stocks.insert().values(id=str(uuid.uuid4()), portfolio_id=row["id"], ts_code=code, **values))
            if shares:
                conn.execute(
                    transactions.insert().values(
                        id=str(uuid.uuid4()),
                        portfolio_id=row["id"],
                        ts_code=code,
                        trade_date=start_date or date.today(),
                        side="buy",
                        shares=shares,
                        price=price,
                        amount=total,
                        stop_loss_point=_num(inv.get("stop_loss_point")),
                        reason="imported initial holding",
                        source="import",
                    )
                )

        control = config.get("risk_control") or {}
        if control:
            conn.execute(
                risk.insert().values(
                    portfolio_id=row["id"],
                    bearable_trading_loss=_num(control.get("bearable_trading_loss"), 0),
                    position_control=_num(control.get("position_control"), 1),
                    reserve_profit=_num(control.get("position_control.reserve_profit"), 0),
                    max_position_size=int(_num(control.get("max_position_size"), 50)),
                    max_position_ratio=_num(control.get("max_position_ratio"), 0),
                    stop_loss_should_check=bool(control.get("stop_loss_point.should_check", True)),
                    stop_loss_n_times_atr=_num(control.get("stop_loss_point.n_times_atr"), 2),
                    stop_loss_should_update=bool(control.get("stop_loss_point.should_update", True)),
                    max_holding_should_check=bool(control.get("max_holding_period.should_check", True)),
                    max_holding_days=int(_num(control.get("max_holding_period.days"), 0)),
                )
            )

        for order, policy in enumerate(config.get("policies") or []):
            params = dict(policy)
            name = params.pop("trade_policy.name", "moving_average")
            conn.execute(
                policies.insert().values(
                    id=str(uuid.uuid4()), portfolio_id=row["id"], name=name, params=params, sort_order=order
                )
            )

        for item in config.get("increase_investments") or []:
            flow_date = _as_date(item.get("date"))
            amount = _num(item.get("amount"))
            if flow_date is None or amount is None:
                continue
            conn.execute(
                flows.insert().values(
                    id=str(uuid.uuid4()),
                    portfolio_id=row["id"],
                    flow_date=flow_date,
                    amount=amount,
                    kind="deposit",
                    note="imported increase_investments",
                )
            )


def _backfill_simulation_trades() -> None:
    conn = op.get_bind()
    runs = sa.table(
        "simulation_runs",
        sa.column("id", sa.String),
        sa.column("portfolio_name", sa.String),
        sa.column("portfolio_id", sa.String),
    )
    portfolios = sa.table("portfolios", sa.column("id", sa.String), sa.column("name", sa.String))
    transactions = sa.table(
        "portfolio_transactions",
        sa.column("id", sa.String),
        sa.column("portfolio_id", sa.String),
        sa.column("simulation_run_id", sa.String),
        sa.column("ts_code", sa.String),
        sa.column("trade_date", sa.Date),
        sa.column("side", sa.String),
        sa.column("shares", sa.Integer),
        sa.column("price", sa.Numeric),
        sa.column("amount", sa.Numeric),
        sa.column("realized_pnl", sa.Numeric),
        sa.column("reason", sa.String),
        sa.column("source", sa.String),
    )

    name_to_id = {r["name"]: r["id"] for r in conn.execute(sa.select(portfolios)).mappings()}
    for run in conn.execute(sa.select(runs)).mappings():
        portfolio_id = name_to_id.get(run["portfolio_name"])
        if portfolio_id:
            conn.execute(runs.update().where(runs.c.id == run["id"]).values(portfolio_id=portfolio_id))

    # Sells (win/loss) become ledger rows; daily holding snapshots are dropped on purpose.
    rows = conn.execute(
        sa.text(
            "SELECT run_id, trade_date, ts_code, hold_shares, sell_price, benefit, reason "
            "FROM simulation_trades WHERE status IN ('win', 'loss')"
        )
    ).mappings()
    for row in rows:
        run = conn.execute(sa.select(runs).where(runs.c.id == row["run_id"])).mappings().first()
        portfolio_id = (run or {}).get("portfolio_id") or name_to_id.get((run or {}).get("portfolio_name"))
        if not portfolio_id:
            continue
        price = _num(row["sell_price"], 0)
        shares = int(row["hold_shares"] or 0)
        conn.execute(
            transactions.insert().values(
                id=str(uuid.uuid4()),
                portfolio_id=portfolio_id,
                simulation_run_id=row["run_id"],
                ts_code=row["ts_code"],
                trade_date=row["trade_date"],
                side="sell",
                shares=shares,
                price=price,
                amount=float(shares) * float(price),
                realized_pnl=_num(row["benefit"]),
                reason=str(row["reason"] or ""),
                source="simulation",
            )
        )


# ---------------------------------------------------------------- downgrade

def downgrade() -> None:
    op.add_column("portfolios", sa.Column("config", sa.JSON(), nullable=True))
    op.create_table(
        "simulation_trades",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("simulation_runs.id"), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=True),
        sa.Column("ts_code", sa.String(16), nullable=True),
        sa.Column("hold_shares", sa.Integer(), nullable=True),
        sa.Column("hold_date", sa.Date(), nullable=True),
        sa.Column("buy_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("sell_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("total_cash_return", sa.Numeric(18, 2), nullable=True),
        sa.Column("benefit", sa.Numeric(18, 2), nullable=True),
        sa.Column("reason", sa.String(255), server_default=""),
        sa.Column("status", sa.String(32), nullable=True),
        if_not_exists=True,
    )
    op.create_index("ix_simulation_trades_run_id", "simulation_trades", ["run_id"], if_not_exists=True)

    conn = op.get_bind()
    portfolios = sa.table(
        "portfolios",
        sa.column("id", sa.String),
        sa.column("name", sa.String),
        sa.column("start_date", sa.Date),
        sa.column("initial_investment", sa.Numeric),
        sa.column("balance", sa.Numeric),
        sa.column("config", sa.JSON),
    )
    stocks = sa.table(
        "portfolio_stocks",
        sa.column("portfolio_id", sa.String),
        sa.column("ts_code", sa.String),
        sa.column("status", sa.String),
        sa.column("hold_shares", sa.Integer),
        sa.column("avg_cost", sa.Numeric),
        sa.column("stop_loss_point", sa.Numeric),
    )
    risk = sa.table(
        "portfolio_risk_controls",
        sa.column("portfolio_id", sa.String),
        sa.column("bearable_trading_loss", sa.Numeric),
        sa.column("position_control", sa.Numeric),
        sa.column("reserve_profit", sa.Numeric),
        sa.column("max_position_size", sa.Integer),
        sa.column("max_position_ratio", sa.Numeric),
        sa.column("stop_loss_should_check", sa.Boolean),
        sa.column("stop_loss_n_times_atr", sa.Numeric),
        sa.column("stop_loss_should_update", sa.Boolean),
        sa.column("max_holding_should_check", sa.Boolean),
        sa.column("max_holding_days", sa.Integer),
    )
    policies = sa.table(
        "portfolio_policies",
        sa.column("portfolio_id", sa.String),
        sa.column("name", sa.String),
        sa.column("params", sa.JSON),
        sa.column("sort_order", sa.Integer),
    )
    flows = sa.table(
        "portfolio_cash_flows",
        sa.column("portfolio_id", sa.String),
        sa.column("flow_date", sa.Date),
        sa.column("amount", sa.Numeric),
    )

    for row in conn.execute(sa.select(portfolios)).mappings():
        pid = row["id"]
        stock_rows = conn.execute(sa.select(stocks).where(stocks.c.portfolio_id == pid)).mappings().all()
        risk_row = conn.execute(sa.select(risk).where(risk.c.portfolio_id == pid)).mappings().first()
        policy_rows = conn.execute(
            sa.select(policies).where(policies.c.portfolio_id == pid).order_by(policies.c.sort_order)
        ).mappings().all()
        flow_rows = conn.execute(
            sa.select(flows).where(flows.c.portfolio_id == pid).order_by(flows.c.flow_date)
        ).mappings().all()

        config = {
            "name": row["name"],
            "start_date": row["start_date"].isoformat() if row["start_date"] else None,
            "initial_investment": float(row["initial_investment"] or 0),
            "balance": float(row["balance"] or 0),
            "follow_stocks": [s["ts_code"] for s in stock_rows if s["status"] != "holding"],
            "investments": [
                {
                    "ts_code": s["ts_code"],
                    "hold_shares": s["hold_shares"],
                    "buy_price": float(s["avg_cost"] or 0),
                    "stop_loss_point": float(s["stop_loss_point"] or 0),
                }
                for s in stock_rows
                if s["status"] == "holding"
            ],
            "increase_investments": [
                {"date": f["flow_date"].isoformat(), "amount": float(f["amount"])} for f in flow_rows
            ],
            "risk_control": {},
            "policies": [],
        }
        if risk_row:
            config["risk_control"] = {
                "bearable_trading_loss": float(risk_row["bearable_trading_loss"] or 0),
                "position_control": float(risk_row["position_control"] or 0),
                "position_control.reserve_profit": float(risk_row["reserve_profit"] or 0),
                "max_position_size": int(risk_row["max_position_size"] or 0),
                "max_position_ratio": float(risk_row["max_position_ratio"] or 0),
                "stop_loss_point.should_check": bool(risk_row["stop_loss_should_check"]),
                "stop_loss_point.n_times_atr": float(risk_row["stop_loss_n_times_atr"] or 0),
                "stop_loss_point.should_update": bool(risk_row["stop_loss_should_update"]),
                "max_holding_period.should_check": bool(risk_row["max_holding_should_check"]),
                "max_holding_period.days": int(risk_row["max_holding_days"] or 0),
            }
        for p in policy_rows:
            config["policies"].append({"trade_policy.name": p["name"], **dict(p["params"] or {})})

        conn.execute(portfolios.update().where(portfolios.c.id == pid).values(config=config))

    op.drop_constraint("fk_simulation_runs_portfolio_id", "simulation_runs", type_="foreignkey")
    op.drop_column("simulation_runs", "portfolio_id")
    op.drop_table("portfolio_cash_flows")
    op.drop_table("portfolio_policies")
    op.drop_table("portfolio_risk_controls")
    op.drop_table("portfolio_transactions")
    op.drop_table("portfolio_stocks")
