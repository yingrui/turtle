"""portfolio holdings/trades — relational storage, aggregates, backtest linkage."""

import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, raise_server_exceptions=True)


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_token():
    login = f"ps_{uuid.uuid4().hex[:8]}"
    client.post("/api/auth/register", json={"login": login, "password": "secret123"})
    res = client.post("/api/auth/login", json={"login": login, "password": "secret123"})
    return res.json()["access_token"]


@pytest.fixture
def portfolio(auth_token):
    name = f"ps{uuid.uuid4().hex[:6]}"
    client.post("/api/portfolios", json={"name": name}, headers=_auth_headers(auth_token))
    return name


def _buy(name, headers, ts_code, shares, price, trade_date="2026-03-02"):
    return client.post(
        f"/api/portfolios/{name}/transactions",
        headers=headers,
        json={"ts_code": ts_code, "side": "buy", "shares": shares, "price": price, "trade_date": trade_date},
    )


def _sell(name, headers, ts_code, shares, price, trade_date="2026-04-01"):
    return client.post(
        f"/api/portfolios/{name}/transactions",
        headers=headers,
        json={"ts_code": ts_code, "side": "sell", "shares": shares, "price": price, "trade_date": trade_date},
    )


def test_created_portfolio_has_no_stocks(portfolio, auth_token):
    headers = _auth_headers(auth_token)
    res = client.get(f"/api/portfolios/{portfolio}/stocks", headers=headers)
    assert res.status_code == 200
    assert res.json()["stocks"] == []


def test_buy_creates_holding_with_weighted_average_cost(portfolio, auth_token):
    headers = _auth_headers(auth_token)
    assert _buy(portfolio, headers, "600519.SH", 100, 10).status_code == 200
    assert _buy(portfolio, headers, "600519.SH", 100, 14, trade_date="2026-03-05").status_code == 200

    stock = client.get(f"/api/portfolios/{portfolio}/stocks", headers=headers).json()["stocks"][0]
    assert stock["status"] == "holding"
    assert stock["hold_shares"] == 200
    assert stock["avg_cost"] == 12.0  # (100*10 + 100*14) / 200
    assert stock["total_cost"] == 2400.0
    assert stock["first_buy_date"] == "2026-03-02"
    assert stock["last_trade_date"] == "2026-03-05"


def test_partial_sell_realizes_pnl_and_keeps_cost_basis(portfolio, auth_token):
    headers = _auth_headers(auth_token)
    _buy(portfolio, headers, "600519.SH", 200, 10)
    res = _sell(portfolio, headers, "600519.SH", 50, 15)
    assert res.status_code == 200
    assert res.json()["realized_pnl"] == 250.0  # (15 - 10) * 50

    stock = client.get(f"/api/portfolios/{portfolio}/stocks", headers=headers).json()["stocks"][0]
    assert stock["hold_shares"] == 150
    assert stock["avg_cost"] == 10.0  # unchanged on sells
    assert stock["total_cost"] == 1500.0
    assert stock["realized_pnl"] == 250.0
    assert stock["status"] == "holding"


def test_full_sell_closes_position(portfolio, auth_token):
    headers = _auth_headers(auth_token)
    _buy(portfolio, headers, "600519.SH", 100, 10)
    _sell(portfolio, headers, "600519.SH", 100, 8)

    stock = client.get(f"/api/portfolios/{portfolio}/stocks", headers=headers).json()["stocks"][0]
    assert stock["hold_shares"] == 0
    assert stock["status"] == "closed"
    assert stock["realized_pnl"] == -200.0

    # closed positions drop out of the engine-facing config
    config = client.get(f"/api/portfolios/{portfolio}", headers=headers).json()
    assert config["follow_stocks"] == []
    assert config["investments"] == []


def test_sell_more_than_held_is_rejected(portfolio, auth_token):
    headers = _auth_headers(auth_token)
    _buy(portfolio, headers, "600519.SH", 100, 10)
    res = _sell(portfolio, headers, "600519.SH", 200, 12)
    assert res.status_code == 400
    assert "Cannot sell" in res.json()["detail"]


def test_aggregates_match_ledger_replay(portfolio, auth_token):
    headers = _auth_headers(auth_token)
    _buy(portfolio, headers, "600519.SH", 300, 11.11)
    _buy(portfolio, headers, "600519.SH", 100, 19.99, trade_date="2026-03-09")
    _sell(portfolio, headers, "600519.SH", 250, 30.5)

    listed = client.get(f"/api/portfolios/{portfolio}/stocks", headers=headers).json()["stocks"][0]
    rebuilt = client.post(f"/api/portfolios/{portfolio}/stocks/600519.SH/rebuild", headers=headers).json()
    # `listed` also carries live quote fields (price, market value, unrealized P&L) that are
    # computed on read; the stored aggregates must match the ledger replay exactly.
    derived = {"current_price", "price_date", "market_value", "unrealized_pnl", "unrealized_pct"}
    assert {k: v for k, v in listed.items() if k not in derived} == rebuilt


def test_holdings_carry_latest_price_and_unrealized_pnl(portfolio, auth_token):
    from fixtures.market_data import SERIES_END, close_on, trade_days

    headers = _auth_headers(auth_token)
    buy_price = 1000.0
    _buy(portfolio, headers, "600519.SH", 100, buy_price)

    stock = client.get(f"/api/portfolios/{portfolio}/stocks", headers=headers).json()["stocks"][0]
    latest_day = trade_days()[-1]
    latest = close_on("600519.SH", SERIES_END)
    assert stock["current_price"] == latest
    assert stock["price_date"] == latest_day.isoformat()
    assert stock["market_value"] == round(latest * 100, 2)
    assert stock["unrealized_pnl"] == round((latest - buy_price) * 100, 2)
    assert stock["unrealized_pct"] == round((latest / buy_price - 1) * 100, 2)


def test_watchlist_rows_have_no_position_metrics(portfolio, auth_token):
    headers = _auth_headers(auth_token)
    client.post(f"/api/portfolios/{portfolio}/watchlist", json={"ts_code": "600519.SH"}, headers=headers)

    stock = client.get(f"/api/portfolios/{portfolio}/stocks", headers=headers).json()["stocks"][0]
    assert stock["status"] == "watching"
    assert "unrealized_pnl" not in stock


def test_transactions_are_recorded_and_filterable(portfolio, auth_token):
    headers = _auth_headers(auth_token)
    _buy(portfolio, headers, "600519.SH", 100, 10)
    _buy(portfolio, headers, "000001.SZ", 200, 5)
    _sell(portfolio, headers, "600519.SH", 100, 12)

    all_txns = client.get(f"/api/portfolios/{portfolio}/transactions", headers=headers).json()["transactions"]
    assert len(all_txns) == 3
    assert {t["side"] for t in all_txns} == {"buy", "sell"}

    only_pf = client.get(
        f"/api/portfolios/{portfolio}/transactions", headers=headers, params={"ts_code": "600519.SH"}
    ).json()["transactions"]
    assert len(only_pf) == 2
    assert only_pf[0]["side"] == "sell"  # newest first


def test_simulation_rows_do_not_touch_live_holdings(portfolio, auth_token, db_session):
    from datetime import date

    from app.models.portfolio import PortfolioTransaction
    from app.services.portfolio_service import PortfolioService

    headers = _auth_headers(auth_token)
    _buy(portfolio, headers, "600519.SH", 100, 10)

    svc = PortfolioService(db_session)
    portfolio_id = svc.get_portfolio_id(portfolio)
    db_session.add(
        PortfolioTransaction(
            id=str(uuid.uuid4()),
            portfolio_id=portfolio_id,
            simulation_run_id=None,
            ts_code="600519.SH",
            trade_date=date(2026, 5, 6),
            side="buy",
            shares=999,
            price=1,
            amount=999,
            source="manual",
        )
    )
    db_session.commit()

    stock = client.get(f"/api/portfolios/{portfolio}/stocks", headers=headers).json()["stocks"][0]
    assert stock["hold_shares"] == 100  # unaffected by direct ledger inserts


def test_backtest_trades_are_linked_to_the_run(portfolio, auth_token, db_session):
    from datetime import date

    from app.models.portfolio import PortfolioTransaction
    from app.models.simulation import SimulationRun
    from app.services.portfolio_service import PortfolioService

    headers = _auth_headers(auth_token)
    svc = PortfolioService(db_session)
    portfolio_id = svc.get_portfolio_id(portfolio)
    run_id = str(uuid.uuid4())
    db_session.add(
        SimulationRun(
            id=run_id,
            job_id=None,
            portfolio_id=portfolio_id,
            portfolio_name=portfolio,
            policy_id=0,
            config_snapshot="{}",
        )
    )
    db_session.add(
        PortfolioTransaction(
            id=str(uuid.uuid4()),
            portfolio_id=portfolio_id,
            simulation_run_id=run_id,
            ts_code="600519.SH",
            trade_date=date(2026, 5, 6),
            side="sell",
            shares=100,
            price=12,
            amount=1200,
            realized_pnl=200,
            source="simulation",
        )
    )
    db_session.commit()

    by_run = client.get(
        f"/api/portfolios/{portfolio}/transactions", headers=headers, params={"simulation_run_id": run_id}
    ).json()["transactions"]
    assert len(by_run) == 1
    assert by_run[0]["source"] == "simulation"
    assert by_run[0]["realized_pnl"] == 200.0


def test_remove_stock_blocked_when_holding(portfolio, auth_token):
    headers = _auth_headers(auth_token)
    client.post(f"/api/portfolios/{portfolio}/watchlist", json={"ts_code": "600519.SH"}, headers=headers)
    res = client.delete(f"/api/portfolios/{portfolio}/stocks/600519.SH", headers=headers)
    assert res.status_code == 200

    _buy(portfolio, headers, "000001.SZ", 100, 10)
    blocked = client.delete(f"/api/portfolios/{portfolio}/stocks/000001.SZ", headers=headers)
    assert blocked.status_code == 400


def test_stock_metadata_patch(portfolio, auth_token):
    headers = _auth_headers(auth_token)
    client.post(f"/api/portfolios/{portfolio}/watchlist", json={"ts_code": "600519.SH"}, headers=headers)
    res = client.patch(
        f"/api/portfolios/{portfolio}/stocks/600519.SH",
        headers=headers,
        json={"target_amount": 50000, "stop_loss_point": 9.5, "max_holding_days": 30, "note": "观察"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["target_amount"] == 50000.0
    assert body["stop_loss_point"] == 9.5
    assert body["max_holding_days"] == 30
    assert body["note"] == "观察"


def test_legacy_config_payload_is_decomposed(portfolio, auth_token):
    headers = _auth_headers(auth_token)
    config = client.get(f"/api/portfolios/{portfolio}", headers=headers).json()
    config["investments"] = [{"ts_code": "600519.SH", "hold_shares": 100, "buy_price": 20}]
    config["risk_control"] = {**config["risk_control"], "max_position_size": 7}
    config["increase_investments"] = [{"date": "2026-02-01", "amount": 5000}]

    saved = client.put(f"/api/portfolios/{portfolio}", headers=headers, json={"config": config})
    assert saved.status_code == 200

    stock = client.get(f"/api/portfolios/{portfolio}/stocks", headers=headers).json()["stocks"][0]
    assert stock["status"] == "holding"
    assert stock["hold_shares"] == 100
    assert stock["avg_cost"] == 20.0
    assert stock["first_buy_date"] == "2024-01-01"

    assert client.get(f"/api/portfolios/{portfolio}/risk-control", headers=headers).json()["max_position_size"] == 7
    flows = client.get(f"/api/portfolios/{portfolio}/cash-flows", headers=headers).json()["cash_flows"]
    assert flows[0]["amount"] == 5000.0


def test_risk_policies_and_cash_flow_endpoints(portfolio, auth_token):
    headers = _auth_headers(auth_token)

    risk = client.put(
        f"/api/portfolios/{portfolio}/risk-control",
        headers=headers,
        json={"risk_control": {"bearable_trading_loss": 0.02, "max_holding_period.days": 45}},
    )
    assert risk.json()["bearable_trading_loss"] == pytest.approx(0.02)
    assert risk.json()["max_holding_period.days"] == 45

    policies = client.get(f"/api/portfolios/{portfolio}/policies", headers=headers).json()["policies"]
    assert policies[0]["name"] == "moving_average"

    replaced = client.put(
        f"/api/portfolios/{portfolio}/policies",
        headers=headers,
        json={"policies": [{"trade_policy.name": "donchian", "trade_policy.donchian.window": 20}]},
    ).json()["policies"]
    assert len(replaced) == 1
    assert replaced[0]["name"] == "donchian"

    created = client.post(
        f"/api/portfolios/{portfolio}/cash-flows",
        headers=headers,
        json={"flow_date": "2026-02-01", "amount": 3000, "kind": "deposit"},
    )
    assert created.status_code == 200
    assert created.json()["amount"] == 3000.0
    assert len(client.get(f"/api/portfolios/{portfolio}/cash-flows", headers=headers).json()["cash_flows"]) == 1


def test_reopening_a_position_restarts_the_holding_period(portfolio, auth_token):
    """Closing and re-buying must not keep the previous streak's first buy date."""
    headers = _auth_headers(auth_token)
    _buy(portfolio, headers, "600519.SH", 100, 10, trade_date="2026-03-02")
    _sell(portfolio, headers, "600519.SH", 100, 12, trade_date="2026-04-01")
    _buy(portfolio, headers, "600519.SH", 100, 8, trade_date="2026-10-12")

    stock = client.get(f"/api/portfolios/{portfolio}/stocks", headers=headers).json()["stocks"][0]
    assert stock["first_buy_date"] == "2026-10-12"
    assert stock["last_trade_date"] == "2026-10-12"
    # holding_days is derived from today, so compare against the new streak rather than a constant
    expected_days = (date.today() - date(2026, 10, 12)).days
    assert stock["holding_days"] == expected_days
    assert stock["holding_days"] < 200  # the old streak (from 2026-03-02) would be ~225
    assert stock["realized_pnl"] == 200.0  # realized P&L still accumulates across streaks
    assert stock["avg_cost"] == 8.0        # cost basis restarts with the new streak

    rebuilt = client.post(f"/api/portfolios/{portfolio}/stocks/600519.SH/rebuild", headers=headers).json()
    assert rebuilt["first_buy_date"] == "2026-10-12"
    assert rebuilt["holding_days"] == expected_days
    assert rebuilt["avg_cost"] == 8.0
    assert rebuilt["realized_pnl"] == 200.0


def test_adding_to_a_position_keeps_the_original_first_buy(portfolio, auth_token):
    headers = _auth_headers(auth_token)
    _buy(portfolio, headers, "600519.SH", 100, 10, trade_date="2026-03-02")
    _buy(portfolio, headers, "600519.SH", 100, 14, trade_date="2026-03-30")

    stock = client.get(f"/api/portfolios/{portfolio}/stocks", headers=headers).json()["stocks"][0]
    assert stock["first_buy_date"] == "2026-03-02"  # unchanged by the add-on buy
    assert stock["last_trade_date"] == "2026-03-30"
    assert stock["avg_cost"] == 12.0


def test_the_stocks_route_accepts_a_portfolio_id(auth_token):
    """An Action webhook targets this path with the ontology's `portfolio_id` — no name needed."""
    from app.database import SessionLocal
    from app.models.portfolio import Portfolio

    headers = _auth_headers(auth_token)
    name = f"byid{uuid.uuid4().hex[:6]}"
    client.post("/api/portfolios", json={"name": name}, headers=headers)
    db = SessionLocal()
    try:
        portfolio_id = db.query(Portfolio).filter(Portfolio.name == name).one().id
    finally:
        db.close()
    by_id = client.post(
        f"/api/portfolios/{portfolio_id}/stocks",
        json={"ts_code": "600519.SH", "target_weight": 0.05},
        headers=headers,
    )
    assert by_id.status_code == 200, by_id.text
    assert by_id.json()["ts_code"] == "600519.SH"
    assert float(by_id.json()["target_weight"]) == 0.05

    listed = client.get(f"/api/portfolios/{portfolio_id}/stocks", headers=headers).json()["stocks"]
    assert [s["ts_code"] for s in listed] == ["600519.SH"]
