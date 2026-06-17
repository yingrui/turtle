import re
import uuid

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.portfolio import Portfolio

_NAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$")

DEFAULT_PORTFOLIO_CONFIG: dict = {
    "name": "portfolio",
    "start_date": "2024-01-01",
    "initial_investment": 150000,
    "balance": 0,
    "follow_stocks": [],
    "investments": [],
    "increase_investments": [],
    "risk_control": {
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
    },
    "policies": [
        {
            "trade_policy.name": "moving_average",
            "trade_policy.moving_average.triple": False,
            "trade_policy.moving_average.window_1": 10,
            "trade_policy.moving_average.window_2": 60,
            "trade_policy.moving_average.should_price_higher_than_ma": True,
        },
    ],
}


class PortfolioService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def validate_name(name: str) -> str:
        name = name.strip()
        if not _NAME_RE.match(name):
            raise ValueError(
                "Portfolio name must start with a letter and contain only letters, digits, _ or -"
            )
        return name

    def list_portfolios(self) -> list[str]:
        rows = self.db.scalars(select(Portfolio.name).order_by(Portfolio.name)).all()
        return list(rows)

    def _get_row(self, name: str) -> Portfolio:
        row = self.db.scalar(select(Portfolio).where(Portfolio.name == name))
        if not row:
            raise FileNotFoundError(f"Portfolio {name} not found")
        return row

    def get_portfolio(self, name: str) -> dict:
        return dict(self._get_row(name).config)

    def create_portfolio(self, name: str, config: dict | None = None) -> dict:
        name = self.validate_name(name)
        existing = self.db.scalar(select(Portfolio).where(Portfolio.name == name))
        if existing:
            raise ValueError(f"Portfolio {name} already exists")
        data = dict(config if config is not None else DEFAULT_PORTFOLIO_CONFIG)
        data["name"] = name
        row = Portfolio(id=str(uuid.uuid4()), name=name, config=data)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return dict(row.config)

    def save_portfolio(self, name: str, data: dict) -> dict:
        row = self._get_row(name)
        if not isinstance(data, dict):
            raise ValueError("Portfolio config must be a mapping")
        data = dict(data)
        data["name"] = name
        row.config = data
        self.db.commit()
        self.db.refresh(row)
        return dict(row.config)

    def get_portfolio_yaml(self, name: str) -> str:
        return yaml.safe_dump(self.get_portfolio(name), allow_unicode=True, sort_keys=False)

    def save_portfolio_yaml(self, name: str, text: str) -> dict:
        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            raise ValueError("Portfolio YAML must be a mapping")
        return self.save_portfolio(name, data)

    def delete_portfolio(self, name: str) -> None:
        row = self._get_row(name)
        self.db.delete(row)
        self.db.commit()

    def add_to_watchlist(self, name: str, ts_code: str) -> dict:
        ts_code = ts_code.strip().upper()
        if not ts_code:
            raise ValueError("ts_code is required")
        config = self.get_portfolio(name)
        stocks = list(config.get("follow_stocks") or [])
        if ts_code not in stocks:
            stocks.append(ts_code)
        config["follow_stocks"] = stocks
        return self.save_portfolio(name, config)

    def add_many_to_watchlist(self, name: str, ts_codes: list[str]) -> dict:
        config = self.get_portfolio(name)
        stocks = list(config.get("follow_stocks") or [])
        for code in ts_codes:
            c = (code or "").strip().upper()
            if c and c not in stocks:
                stocks.append(c)
        config["follow_stocks"] = stocks
        return self.save_portfolio(name, config)

    def remove_from_watchlist(self, name: str, ts_code: str) -> dict:
        ts_code = ts_code.strip().upper()
        config = self.get_portfolio(name)
        stocks = [c for c in (config.get("follow_stocks") or []) if c != ts_code]
        config["follow_stocks"] = stocks
        return self.save_portfolio(name, config)

    def list_watchlist_with_quotes(self) -> dict:
        from app.core.engine import stock_universe

        code_to_portfolios: dict[str, list[str]] = {}
        rows = self.db.scalars(select(Portfolio).order_by(Portfolio.name)).all()
        for row in rows:
            for code in row.config.get("follow_stocks") or []:
                c = str(code).strip().upper()
                if not c:
                    continue
                code_to_portfolios.setdefault(c, [])
                if row.name not in code_to_portfolios[c]:
                    code_to_portfolios[c].append(row.name)

        if not code_to_portfolios:
            return {"as_of_date": None, "items": []}

        ts_codes = list(code_to_portfolios.keys())
        items = stock_universe.get_quotes_for_codes(ts_codes)
        for item in items:
            item["portfolios"] = code_to_portfolios.get(item["ts_code"], [])
        items.sort(key=lambda x: x.get("ts_code", ""))
        as_of = items[0].get("quote", {}).get("trade_date") if items else None
        return {"as_of_date": as_of, "items": items}

    def list_portfolio_watchlist_with_quotes(self, name: str) -> dict:
        from app.core.engine import stock_universe

        config = self.get_portfolio(name)
        ts_codes = [
            str(c).strip().upper()
            for c in (config.get("follow_stocks") or [])
            if str(c).strip()
        ]
        if not ts_codes:
            return {"portfolio": name, "as_of_date": None, "items": []}

        items = stock_universe.get_quotes_for_codes(ts_codes)
        items.sort(key=lambda x: x.get("ts_code", ""))
        as_of = items[0].get("quote", {}).get("trade_date") if items else None
        return {"portfolio": name, "as_of_date": as_of, "items": items}
