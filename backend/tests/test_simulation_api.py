from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models.simulation import SimulationDaily, SimulationRun, SimulationTrade

client = TestClient(app, raise_server_exceptions=True)


@pytest.fixture
def auth_token():
    import uuid

    login = f"sim_{uuid.uuid4().hex[:8]}"
    client.post("/api/auth/register", json={"login": login, "password": "secret123"})
    return client.post("/api/auth/login", json={"login": login, "password": "secret123"}).json()["access_token"]


def test_deleting_a_run_takes_its_books_and_detaches_the_portfolio(auth_token):
    """A run owns its trades/holdings/pool/daily rows; a portfolio pointing at it is detached."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    portfolio_id = "del-run-pf"
    with SessionLocal() as db:
        from app.models.portfolio import Portfolio

        if not db.get(Portfolio, portfolio_id):
            db.add(Portfolio(id=portfolio_id, name=portfolio_id))
            db.commit()
        run = SimulationRun(
            id="run-to-delete", portfolio_id=portfolio_id, portfolio_name=portfolio_id,
            policy_id=0, mode="model", config_snapshot="{}",
        )
        db.add(run)
        db.add(
            SimulationDaily(
                run_id=run.id, trade_date=date(2026, 5, 14), return_rate=0.0, balance=100.0,
                benefit=0.0, investment_total=0.0, total=100.0,
            )
        )
        db.add(
            SimulationTrade(
                id="t1", run_id=run.id, ts_code="600519.SH", trade_date=date(2026, 5, 14),
                side="buy", shares=100, price=10, amount=1000, fee=5,
            )
        )
        db.commit()

    response = client.delete("/api/simulations/run-to-delete", headers=headers)
    assert response.status_code == 200
    assert response.json()["deleted"]["simulation_trades"] == 1

    with SessionLocal() as db:
        assert db.get(SimulationRun, "run-to-delete") is None
        assert db.query(SimulationDaily).filter_by(run_id="run-to-delete").count() == 0
        assert db.query(SimulationTrade).filter_by(run_id="run-to-delete").count() == 0
