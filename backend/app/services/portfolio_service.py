import re
import uuid
from datetime import date, datetime
from decimal import Decimal

import yaml
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.portfolio import (
    Portfolio,
    PortfolioCashFlow,
    PortfolioPolicy,
    PortfolioRiskControl,
    PortfolioStock,
    PortfolioTransaction,
)

_NAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$")

SIDES = ("buy", "sell")
STATUSES = ("watching", "holding", "closed")

DEFAULT_START_DATE = "2024-01-01"
DEFAULT_INITIAL_INVESTMENT = 150000

# Engine-facing shape; `risk_control` keys are flattened with dots.
DEFAULT_RISK_CONTROL: dict = {
    "bearable_trading_loss": 0.01,
    "position_control": 1.0,
    "position_control.reserve_profit": 0,
    "max_position_size": 50,
    "max_position_ratio": 0.5,
    "stop_loss_point.should_check": True,
    "stop_loss_point.n_times_atr": 2,
    "stop_loss_point.should_update": True,
    "max_holding_period.should_check": True,
    "max_holding_period.days": 80,
}

DEFAULT_POLICIES: list[dict] = [
    {
        "trade_policy.name": "moving_average",
        "trade_policy.moving_average.triple": False,
        "trade_policy.moving_average.window_1": 10,
        "trade_policy.moving_average.window_2": 60,
        "trade_policy.moving_average.should_price_higher_than_ma": True,
    },
]

DEFAULT_PORTFOLIO_CONFIG: dict = {
    "name": "portfolio",
    "start_date": DEFAULT_START_DATE,
    "initial_investment": DEFAULT_INITIAL_INVESTMENT,
    "balance": 0,
    "follow_stocks": [],
    "investments": [],
    "increase_investments": [],
    "risk_control": DEFAULT_RISK_CONTROL,
    "policies": DEFAULT_POLICIES,
}

# Flattened risk_control key ⇄ column
_RISK_FIELDS = {
    "bearable_trading_loss": "bearable_trading_loss",
    "position_control": "position_control",
    "position_control.reserve_profit": "reserve_profit",
    "max_position_size": "max_position_size",
    "max_position_ratio": "max_position_ratio",
    "stop_loss_point.should_check": "stop_loss_should_check",
    "stop_loss_point.n_times_atr": "stop_loss_n_times_atr",
    "stop_loss_point.should_update": "stop_loss_should_update",
    "max_holding_period.should_check": "max_holding_should_check",
    "max_holding_period.days": "max_holding_days",
}

_EDITABLE_STOCK_FIELDS = (
    "status",
    "target_amount",
    "target_weight",
    "stop_loss_point",
    "max_holding_days",
    "atr",
    "note",
)


def _dec(value, default: str = "0") -> Decimal:
    if value is None or value == "":
        return Decimal(default)
    return Decimal(str(value))


def _q(value: Decimal, places: str = "0.0001") -> Decimal:
    return value.quantize(Decimal(places))


def _num(value) -> float | None:
    return None if value is None else float(value)


def _as_date(value) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return date.fromisoformat(str(value)[:10])


def _as_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


class PortfolioService:
    """Portfolio storage.

    Holdings/trades live in relational tables. ``get_portfolio`` composes the legacy
    config dict (name, start_date, follow_stocks, investments, risk_control, policies)
    so the trading engine and existing callers keep their input shape.
    """

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------ helpers

    @staticmethod
    def validate_name(name: str) -> str:
        name = name.strip()
        if not _NAME_RE.match(name):
            raise ValueError(
                "Portfolio name must start with a letter and contain only letters, digits, _ or -"
            )
        return name

    def _get_row(self, name: str) -> Portfolio:
        row = self.db.scalar(select(Portfolio).where(Portfolio.name == name))
        if not row:
            raise FileNotFoundError(f"Portfolio {name} not found")
        return row

    def _stocks(self, portfolio_id: str) -> list[PortfolioStock]:
        return list(
            self.db.scalars(
                select(PortfolioStock)
                .where(PortfolioStock.portfolio_id == portfolio_id)
                .order_by(PortfolioStock.ts_code)
            ).all()
        )

    def _get_stock(self, portfolio_id: str, ts_code: str) -> PortfolioStock | None:
        return self.db.scalar(
            select(PortfolioStock).where(
                PortfolioStock.portfolio_id == portfolio_id,
                PortfolioStock.ts_code == ts_code,
            )
        )

    def _risk_row(self, portfolio_id: str) -> PortfolioRiskControl | None:
        return self.db.get(PortfolioRiskControl, portfolio_id)

    def _policy_rows(self, portfolio_id: str) -> list[PortfolioPolicy]:
        return list(
            self.db.scalars(
                select(PortfolioPolicy)
                .where(PortfolioPolicy.portfolio_id == portfolio_id)
                .order_by(PortfolioPolicy.sort_order, PortfolioPolicy.created_at)
            ).all()
        )

    def _flow_rows(self, portfolio_id: str) -> list[PortfolioCashFlow]:
        return list(
            self.db.scalars(
                select(PortfolioCashFlow)
                .where(PortfolioCashFlow.portfolio_id == portfolio_id)
                .order_by(PortfolioCashFlow.flow_date)
            ).all()
        )

    def _ensure_risk_row(self, portfolio_id: str, defaults: dict | None = None) -> PortfolioRiskControl:
        row = self._risk_row(portfolio_id)
        if row is None:
            row = PortfolioRiskControl(portfolio_id=portfolio_id)
            self._apply_risk_dict(row, defaults or DEFAULT_RISK_CONTROL)
            self.db.add(row)
        return row

    @staticmethod
    def _apply_risk_dict(row: PortfolioRiskControl, data: dict) -> None:
        for flat_key, column in _RISK_FIELDS.items():
            if flat_key not in data or data[flat_key] is None:
                continue
            value = data[flat_key]
            if column in ("max_position_size", "max_holding_days"):
                setattr(row, column, int(value))
            elif column.startswith("stop_loss_should") or column == "max_holding_should_check":
                setattr(row, column, _as_bool(value, True))
            else:
                setattr(row, column, _dec(value))
        # `max_position_size` may arrive as the bare column name too (new-style payloads).
        for column in ("bearable_trading_loss", "position_control", "max_position_size", "max_position_ratio"):
            if column in data and data[column] is not None:
                value = data[column]
                setattr(row, column, int(value) if column == "max_position_size" else _dec(value))

    def _risk_dict(self, portfolio_id: str) -> dict:
        row = self._risk_row(portfolio_id)
        if row is None:
            return dict(DEFAULT_RISK_CONTROL)
        return {
            "bearable_trading_loss": float(row.bearable_trading_loss or 0),
            "position_control": float(row.position_control or 0),
            "position_control.reserve_profit": float(row.reserve_profit or 0),
            "max_position_size": int(row.max_position_size or 0),
            "max_position_ratio": float(row.max_position_ratio or 0),
            "stop_loss_point.should_check": bool(row.stop_loss_should_check),
            "stop_loss_point.n_times_atr": float(row.stop_loss_n_times_atr or 0),
            "stop_loss_point.should_update": bool(row.stop_loss_should_update),
            "max_holding_period.should_check": bool(row.max_holding_should_check),
            "max_holding_period.days": int(row.max_holding_days or 0),
        }

    def _policy_dicts(self, portfolio_id: str) -> list[dict]:
        rows = self._policy_rows(portfolio_id)
        if not rows:
            return [dict(p) for p in DEFAULT_POLICIES]
        return [{"trade_policy.name": r.name, **dict(r.params or {})} for r in rows]

    def _replace_policies(self, portfolio_id: str, policies: list[dict]) -> None:
        self.db.execute(delete(PortfolioPolicy).where(PortfolioPolicy.portfolio_id == portfolio_id))
        for order, policy in enumerate(policies or []):
            params = dict(policy or {})
            name = str(params.pop("trade_policy.name", "moving_average"))
            self.db.add(
                PortfolioPolicy(
                    id=str(uuid.uuid4()),
                    portfolio_id=portfolio_id,
                    name=name,
                    params=params,
                    sort_order=order,
                )
            )

    def _replace_cash_flows(self, portfolio_id: str, flows: list[dict]) -> None:
        self.db.execute(delete(PortfolioCashFlow).where(PortfolioCashFlow.portfolio_id == portfolio_id))
        for item in flows or []:
            flow_date = _as_date(item.get("date") or item.get("flow_date"))
            amount = item.get("amount")
            if flow_date is None or amount is None:
                continue
            self.db.add(
                PortfolioCashFlow(
                    id=str(uuid.uuid4()),
                    portfolio_id=portfolio_id,
                    flow_date=flow_date,
                    amount=_dec(amount, "0.00"),
                    kind=str(item.get("kind") or "deposit"),
                    note=str(item.get("note") or ""),
                )
            )

    @staticmethod
    def stock_to_dict(row: PortfolioStock) -> dict:
        first_buy = row.first_buy_date
        holding_days = None
        if first_buy and row.status == "holding":
            holding_days = (date.today() - first_buy).days
        return {
            "id": row.id,
            "portfolio_id": row.portfolio_id,
            "ts_code": row.ts_code,
            "status": row.status,
            "hold_shares": row.hold_shares,
            "avg_cost": _num(row.avg_cost) or 0,
            "total_cost": _num(row.total_cost) or 0,
            "target_amount": _num(row.target_amount),
            "target_weight": _num(row.target_weight),
            "realized_pnl": _num(row.realized_pnl) or 0,
            "first_buy_date": first_buy.isoformat() if first_buy else None,
            "last_trade_date": row.last_trade_date.isoformat() if row.last_trade_date else None,
            "holding_days": holding_days,
            "stop_loss_point": _num(row.stop_loss_point),
            "max_holding_days": row.max_holding_days,
            "atr": _num(row.atr),
            "note": row.note or "",
        }

    @staticmethod
    def transaction_to_dict(row: PortfolioTransaction) -> dict:
        return {
            "id": row.id,
            "portfolio_id": row.portfolio_id,
            "simulation_run_id": row.simulation_run_id,
            "ts_code": row.ts_code,
            "trade_date": row.trade_date.isoformat() if row.trade_date else None,
            "side": row.side,
            "shares": row.shares,
            "price": _num(row.price) or 0,
            "amount": _num(row.amount) or 0,
            "fee": _num(row.fee) or 0,
            "tax": _num(row.tax) or 0,
            "realized_pnl": _num(row.realized_pnl),
            "stop_loss_point": _num(row.stop_loss_point),
            "reason": row.reason or "",
            "source": row.source,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    # ------------------------------------------------------------ config view

    def compose_config(self, row: Portfolio) -> dict:
        stocks = self._stocks(row.id)
        flows = self._flow_rows(row.id)
        return {
            "name": row.name,
            "start_date": row.start_date.isoformat() if row.start_date else None,
            "initial_investment": _num(row.initial_investment) or 0,
            "balance": _num(row.balance) or 0,
            # held stocks stay monitored, so everything except closed positions is "followed"
            "follow_stocks": [s.ts_code for s in stocks if s.status != "closed"],
            "investments": [
                {
                    "ts_code": s.ts_code,
                    "hold_shares": s.hold_shares,
                    "buy_price": _num(s.avg_cost) or 0,
                    "stop_loss_point": _num(s.stop_loss_point) or 0,
                }
                for s in stocks
                if s.status == "holding" and s.hold_shares
            ],
            "increase_investments": [
                {"date": f.flow_date.isoformat(), "amount": _num(f.amount) or 0} for f in flows
            ],
            "risk_control": self._risk_dict(row.id),
            "policies": self._policy_dicts(row.id),
        }

    # ------------------------------------------------------------ portfolios

    def list_portfolios(self) -> list[str]:
        return list(self.db.scalars(select(Portfolio.name).order_by(Portfolio.name)).all())

    def get_portfolio(self, name: str) -> dict:
        return self.compose_config(self._get_row(name))

    def get_portfolio_id(self, name: str) -> str:
        return self._get_row(name).id

    def create_portfolio(self, name: str, config: dict | None = None) -> dict:
        name = self.validate_name(name)
        if self.db.scalar(select(Portfolio).where(Portfolio.name == name)):
            raise ValueError(f"Portfolio {name} already exists")
        data = dict(config if config is not None else DEFAULT_PORTFOLIO_CONFIG)
        data["name"] = name
        row = Portfolio(
            id=str(uuid.uuid4()),
            name=name,
            start_date=_as_date(data.get("start_date")) or date.fromisoformat(DEFAULT_START_DATE),
            initial_investment=_dec(data.get("initial_investment"), str(DEFAULT_INITIAL_INVESTMENT)),
            balance=_dec(data.get("balance"), "0"),
        )
        self.db.add(row)
        self.db.flush()
        self._ensure_risk_row(row.id, data.get("risk_control"))
        self._replace_policies(row.id, data.get("policies") or DEFAULT_POLICIES)
        self._replace_cash_flows(row.id, data.get("increase_investments") or [])
        self._apply_config_stocks(row.id, data)
        self.db.commit()
        self.db.refresh(row)
        return self.compose_config(row)

    def save_portfolio(self, name: str, data: dict) -> dict:
        row = self._get_row(name)
        if not isinstance(data, dict):
            raise ValueError("Portfolio config must be a mapping")
        data = dict(data)
        data["name"] = name
        if data.get("start_date"):
            row.start_date = _as_date(data["start_date"])
        if data.get("initial_investment") is not None:
            row.initial_investment = _dec(data["initial_investment"])
        if data.get("balance") is not None:
            row.balance = _dec(data["balance"])
        if "risk_control" in data:
            self._apply_risk_dict(self._ensure_risk_row(row.id), data.get("risk_control") or {})
        if "policies" in data:
            self._replace_policies(row.id, data.get("policies") or [])
        if "increase_investments" in data:
            self._replace_cash_flows(row.id, data.get("increase_investments") or [])
        if "follow_stocks" in data or "investments" in data:
            self._apply_config_stocks(row.id, data)
        self.db.commit()
        self.db.refresh(row)
        return self.compose_config(row)

    def _apply_config_stocks(self, portfolio_id: str, data: dict) -> None:
        """Reconcile holdings/watchlist from a config-shaped payload.

        Positions set here are authoritative (config editor is an administrator path); they do
        not create trade rows unless the stock has no ledger history at all, in which case one
        ``source='import'`` buy row is written so the ledger is not empty for that position.
        """
        wanted: dict[str, dict] = {}
        for ts_code in data.get("follow_stocks") or []:
            code = str(ts_code).strip().upper()
            if code:
                wanted.setdefault(code, {})
        for inv in data.get("investments") or []:
            code = str(inv.get("ts_code") or "").strip().upper()
            if not code:
                continue
            shares = int(inv.get("hold_shares") or 0)
            price = _dec(inv.get("buy_price"), "0")
            wanted[code] = {
                "shares": shares,
                "price": price,
                "stop_loss_point": _num(inv.get("stop_loss_point")),
            }

        start_date = None
        row = self.db.get(Portfolio, portfolio_id)
        if row is not None:
            start_date = row.start_date

        for code, spec in wanted.items():
            stock = self._get_stock(portfolio_id, code)
            if stock is None:
                stock = PortfolioStock(id=str(uuid.uuid4()), portfolio_id=portfolio_id, ts_code=code)
                self.db.add(stock)
                self.db.flush()
            shares = spec.get("shares")
            if shares is None:
                if stock.status == "closed":
                    stock.status = "watching"
                continue
            price = spec["price"]
            # Re-establishing a position from the config/YAML editor starts a new holding streak.
            if shares and stock.hold_shares == 0:
                stock.first_buy_date = start_date
            stock.hold_shares = shares
            stock.avg_cost = _q(price)
            stock.total_cost = _q(price * shares)
            stock.stop_loss_point = (
                _dec(spec["stop_loss_point"]) if spec.get("stop_loss_point") is not None else stock.stop_loss_point
            )
            stock.status = "holding" if shares else "watching"
            if shares:
                stock.last_trade_date = start_date
                if not self._has_transactions(portfolio_id, code):
                    self.db.add(
                        PortfolioTransaction(
                            id=str(uuid.uuid4()),
                            portfolio_id=portfolio_id,
                            ts_code=code,
                            trade_date=start_date or date.today(),
                            side="buy",
                            shares=shares,
                            price=price,
                            amount=_q(price * shares, "0.01"),
                            stop_loss_point=stock.stop_loss_point,
                            reason="imported holding",
                            source="import",
                        )
                    )

        for stock in self._stocks(portfolio_id):
            if stock.ts_code in wanted:
                continue
            if stock.hold_shares:
                continue
            if self._has_transactions(portfolio_id, stock.ts_code):
                continue
            self.db.delete(stock)

    def _has_transactions(self, portfolio_id: str, ts_code: str) -> bool:
        return (
            self.db.scalar(
                select(PortfolioTransaction.id)
                .where(
                    PortfolioTransaction.portfolio_id == portfolio_id,
                    PortfolioTransaction.ts_code == ts_code,
                )
                .limit(1)
            )
            is not None
        )

    def get_portfolio_yaml(self, name: str) -> str:
        return yaml.safe_dump(self.get_portfolio(name), allow_unicode=True, sort_keys=False)

    def save_portfolio_yaml(self, name: str, text: str) -> dict:
        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            raise ValueError("Portfolio YAML must be a mapping")
        return self.save_portfolio(name, data)

    def delete_portfolio(self, name: str) -> None:
        self.db.delete(self._get_row(name))
        self.db.commit()

    # ------------------------------------------------------------ stocks

    def list_stocks(self, name: str, with_quotes: bool = True) -> list[dict]:
        row = self._get_row(name)
        stocks = [self.stock_to_dict(s) for s in self._stocks(row.id)]
        if with_quotes:
            self._attach_quotes(stocks)
        return stocks

    @staticmethod
    def _attach_quotes(stocks: list[dict]) -> None:
        """Add latest close, market value and unrealized P&L for held positions.

        Prices come from the market-data tables (latest trade date), so one batch query covers
        every held code; the derived numbers are computed on read and never stored.
        """
        from app.core.engine import stock_universe

        codes = [s["ts_code"] for s in stocks if s["hold_shares"] and s["status"] == "holding"]
        if not codes:
            return
        quotes = {q["ts_code"]: q.get("quote") or {} for q in stock_universe.get_quotes_for_codes(codes)}
        for stock in stocks:
            quote = quotes.get(stock["ts_code"]) or {}
            price = quote.get("close")
            if price is None:
                continue
            shares = stock["hold_shares"]
            avg_cost = stock["avg_cost"]
            stock["current_price"] = float(price)
            stock["price_date"] = quote.get("trade_date")
            stock["market_value"] = round(float(price) * shares, 2)
            stock["unrealized_pnl"] = round((float(price) - avg_cost) * shares, 2)
            stock["unrealized_pct"] = round((float(price) / avg_cost - 1) * 100, 2) if avg_cost else None

    def get_stock(self, name: str, ts_code: str) -> dict:
        row = self._get_row(name)
        stock = self._get_stock(row.id, ts_code.strip().upper())
        if stock is None:
            raise FileNotFoundError(f"{ts_code} is not in portfolio {name}")
        return self.stock_to_dict(stock)

    def upsert_stock(self, name: str, ts_code: str, fields: dict) -> dict:
        row = self._get_row(name)
        code = ts_code.strip().upper()
        if not code:
            raise ValueError("ts_code is required")
        stock = self._get_stock(row.id, code)
        if stock is None:
            stock = PortfolioStock(id=str(uuid.uuid4()), portfolio_id=row.id, ts_code=code, status="watching")
            self.db.add(stock)
        self.update_stock_fields(stock, fields)
        self.db.commit()
        self.db.refresh(stock)
        return self.stock_to_dict(stock)

    def update_stock_fields(self, stock: PortfolioStock, fields: dict) -> None:
        for key in _EDITABLE_STOCK_FIELDS:
            if key not in fields or fields[key] is None:
                continue
            value = fields[key]
            if key == "status":
                if value not in STATUSES:
                    raise ValueError(f"status must be one of {', '.join(STATUSES)}")
                stock.status = value
            elif key in ("target_amount", "target_weight", "stop_loss_point", "atr"):
                setattr(stock, key, _dec(value))
            elif key == "max_holding_days":
                stock.max_holding_days = int(value)
            else:
                stock.note = str(value)

    def remove_stock(self, name: str, ts_code: str) -> None:
        row = self._get_row(name)
        code = ts_code.strip().upper()
        stock = self._get_stock(row.id, code)
        if stock is None:
            raise FileNotFoundError(f"{ts_code} is not in portfolio {name}")
        if stock.hold_shares or self._has_transactions(row.id, code):
            raise ValueError("Cannot remove a stock with holdings or trade history; close it instead")
        self.db.delete(stock)
        self.db.commit()

    # ------------------------------------------------------------ watchlist (delegates)

    def add_to_watchlist(self, name: str, ts_code: str) -> dict:
        """Adds a stock to the portfolio and returns the composed config (legacy API shape)."""
        self.upsert_stock(name, ts_code, {})
        return self.get_portfolio(name)

    def add_many_to_watchlist(self, name: str, ts_codes: list[str]) -> dict:
        row = self._get_row(name)
        for code in ts_codes:
            c = (code or "").strip().upper()
            if not c:
                continue
            if self._get_stock(row.id, c) is None:
                self.db.add(
                    PortfolioStock(id=str(uuid.uuid4()), portfolio_id=row.id, ts_code=c, status="watching")
                )
        self.db.commit()
        return self.get_portfolio(name)

    def remove_from_watchlist(self, name: str, ts_code: str) -> dict:
        self.remove_stock(name, ts_code)
        return self.get_portfolio(name)

    def list_watchlist_with_quotes(self) -> dict:
        from app.core.engine import stock_universe

        code_to_portfolios: dict[str, list[str]] = {}
        rows = self.db.scalars(select(Portfolio).order_by(Portfolio.name)).all()
        for row in rows:
            for stock in self._stocks(row.id):
                if stock.status == "closed":
                    continue
                code_to_portfolios.setdefault(stock.ts_code, [])
                if row.name not in code_to_portfolios[stock.ts_code]:
                    code_to_portfolios[stock.ts_code].append(row.name)

        if not code_to_portfolios:
            return {"as_of_date": None, "items": []}

        items = stock_universe.get_quotes_for_codes(list(code_to_portfolios.keys()))
        for item in items:
            item["portfolios"] = code_to_portfolios.get(item["ts_code"], [])
        items.sort(key=lambda x: x.get("ts_code", ""))
        as_of = items[0].get("quote", {}).get("trade_date") if items else None
        return {"as_of_date": as_of, "items": items}

    def list_portfolio_watchlist_with_quotes(self, name: str) -> dict:
        from app.core.engine import stock_universe

        row = self._get_row(name)
        ts_codes = [s.ts_code for s in self._stocks(row.id) if s.status != "closed"]
        if not ts_codes:
            return {"portfolio": name, "as_of_date": None, "items": []}

        items = stock_universe.get_quotes_for_codes(ts_codes)
        items.sort(key=lambda x: x.get("ts_code", ""))
        as_of = items[0].get("quote", {}).get("trade_date") if items else None
        return {"portfolio": name, "as_of_date": as_of, "items": items}

    # ------------------------------------------------------------ transactions

    def record_transaction(self, name: str, payload: dict) -> dict:
        """Insert a trade and update the derived position aggregates in the same transaction."""
        row = self._get_row(name)
        return self.record_transaction_for(row.id, payload)

    def record_transaction_for(self, portfolio_id: str, payload: dict) -> dict:
        side = str(payload.get("side") or "").strip().lower()
        if side not in SIDES:
            raise ValueError("side must be 'buy' or 'sell'")
        code = str(payload.get("ts_code") or "").strip().upper()
        if not code:
            raise ValueError("ts_code is required")
        trade_date = _as_date(payload.get("trade_date")) or date.today()
        shares = int(payload.get("shares") or 0)
        if shares <= 0:
            raise ValueError("shares must be positive")
        price = _dec(payload.get("price"))
        if price < 0:
            raise ValueError("price must not be negative")
        amount = _dec(payload.get("amount")) if payload.get("amount") is not None else _q(price * shares, "0.01")

        stock = self._get_stock(portfolio_id, code)
        if stock is None:
            stock = PortfolioStock(id=str(uuid.uuid4()), portfolio_id=portfolio_id, ts_code=code, status="watching")
            self.db.add(stock)
            self.db.flush()

        realized: Decimal | None = None
        if side == "buy":
            # A buy that starts from zero shares opens a new holding streak, so the holding
            # period restarts (a previous streak's first buy must not leak into this one).
            if stock.hold_shares == 0:
                stock.first_buy_date = trade_date
            new_shares = stock.hold_shares + shares
            new_cost = _dec(stock.total_cost) + amount
            avg = _q(new_cost / new_shares)
            stock.hold_shares = new_shares
            stock.avg_cost = avg
            stock.total_cost = _q(avg * new_shares)
            stock.status = "holding"
        else:
            if shares > stock.hold_shares:
                raise ValueError(f"Cannot sell {shares} shares; holding only {stock.hold_shares}")
            avg = _dec(stock.avg_cost)
            realized = _q((price - avg) * shares, "0.01")
            stock.realized_pnl = _q(_dec(stock.realized_pnl) + realized, "0.01")
            stock.hold_shares -= shares
            stock.total_cost = _q(avg * stock.hold_shares)
            if stock.hold_shares == 0:
                stock.status = "closed"
        stock.last_trade_date = trade_date

        txn = PortfolioTransaction(
            id=str(uuid.uuid4()),
            portfolio_id=portfolio_id,
            simulation_run_id=payload.get("simulation_run_id"),
            ts_code=code,
            trade_date=trade_date,
            side=side,
            shares=shares,
            price=price,
            amount=amount,
            fee=_dec(payload.get("fee"), "0.00"),
            tax=_dec(payload.get("tax"), "0.00"),
            realized_pnl=realized,
            stop_loss_point=(
                _dec(payload["stop_loss_point"]) if payload.get("stop_loss_point") is not None else stock.stop_loss_point
            ),
            reason=str(payload.get("reason") or ""),
            source=str(payload.get("source") or "manual"),
        )
        self.db.add(txn)
        self.db.commit()
        self.db.refresh(txn)
        return self.transaction_to_dict(txn)

    def list_transactions(
        self,
        name: str,
        ts_code: str | None = None,
        simulation_run_id: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[dict]:
        row = self._get_row(name)
        stmt = (
            select(PortfolioTransaction)
            .where(PortfolioTransaction.portfolio_id == row.id)
            .order_by(PortfolioTransaction.trade_date.desc(), PortfolioTransaction.created_at.desc())
        )
        if ts_code:
            stmt = stmt.where(PortfolioTransaction.ts_code == ts_code.strip().upper())
        if simulation_run_id:
            stmt = stmt.where(PortfolioTransaction.simulation_run_id == simulation_run_id)
        stmt = stmt.limit(limit).offset(offset)
        return [self.transaction_to_dict(t) for t in self.db.scalars(stmt).all()]

    def rebuild_stock_from_transactions(self, name: str, ts_code: str) -> dict:
        """Recompute position aggregates by replaying the ledger (repair / test oracle)."""
        row = self._get_row(name)
        code = ts_code.strip().upper()
        stock = self._get_stock(row.id, code)
        if stock is None:
            raise FileNotFoundError(f"{ts_code} is not in portfolio {name}")
        txns = self.db.scalars(
            select(PortfolioTransaction)
            .where(
                PortfolioTransaction.portfolio_id == row.id,
                PortfolioTransaction.ts_code == code,
            )
            .order_by(PortfolioTransaction.trade_date, PortfolioTransaction.created_at)
        ).all()

        shares = 0
        total_cost = Decimal("0")
        avg = Decimal("0")
        realized = Decimal("0")
        first_buy: date | None = None
        last_trade: date | None = None
        for t in txns:
            amount = _dec(t.amount)
            if t.side == "buy":
                if shares == 0:
                    first_buy = t.trade_date  # start of the current streak
                shares += t.shares
                total_cost += amount
                avg = _q(total_cost / shares) if shares else Decimal("0")
                total_cost = _q(avg * shares)
            else:
                shares -= t.shares
                realized += _q((_dec(t.price) - avg) * t.shares, "0.01")
                total_cost = _q(avg * shares)
                if shares == 0:
                    first_buy = None
            last_trade = t.trade_date

        stock.hold_shares = shares
        stock.avg_cost = avg
        stock.total_cost = total_cost
        stock.realized_pnl = _q(realized, "0.01")
        stock.first_buy_date = first_buy
        stock.last_trade_date = last_trade
        stock.status = "holding" if shares else ("closed" if txns else stock.status)
        self.db.commit()
        self.db.refresh(stock)
        return self.stock_to_dict(stock)

    # ------------------------------------------------------------ risk / policies / cash

    def get_risk_control(self, name: str) -> dict:
        return self._risk_dict(self._get_row(name).id)

    def update_risk_control(self, name: str, data: dict) -> dict:
        row = self._get_row(name)
        self._apply_risk_dict(self._ensure_risk_row(row.id), data or {})
        self.db.commit()
        return self._risk_dict(row.id)

    def list_policies(self, name: str) -> list[dict]:
        row = self._get_row(name)
        return [
            {"id": p.id, "name": p.name, "params": dict(p.params or {}), "sort_order": p.sort_order}
            for p in self._policy_rows(row.id)
        ]

    def replace_policies(self, name: str, policies: list[dict]) -> list[dict]:
        row = self._get_row(name)
        self._replace_policies(row.id, policies or [])
        self.db.commit()
        return self.list_policies(name)

    def list_cash_flows(self, name: str) -> list[dict]:
        row = self._get_row(name)
        return [
            {
                "id": f.id,
                "flow_date": f.flow_date.isoformat(),
                "amount": _num(f.amount) or 0,
                "kind": f.kind,
                "note": f.note or "",
            }
            for f in self._flow_rows(row.id)
        ]

    def create_cash_flow(self, name: str, payload: dict) -> dict:
        row = self._get_row(name)
        flow_date = _as_date(payload.get("flow_date") or payload.get("date"))
        if flow_date is None:
            raise ValueError("flow_date is required")
        amount = _dec(payload.get("amount"))
        flow = PortfolioCashFlow(
            id=str(uuid.uuid4()),
            portfolio_id=row.id,
            flow_date=flow_date,
            amount=amount,
            kind=str(payload.get("kind") or "deposit"),
            note=str(payload.get("note") or ""),
        )
        self.db.add(flow)
        self.db.commit()
        self.db.refresh(flow)
        return {
            "id": flow.id,
            "flow_date": flow.flow_date.isoformat(),
            "amount": _num(flow.amount) or 0,
            "kind": flow.kind,
            "note": flow.note or "",
        }
