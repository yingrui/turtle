"""The pool, the rules, and the membership history they produce."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.models import Portfolio, PortfolioStock, PortfolioStockEvent
from app.services.portfolio_lifecycle_service import (
    LifecycleError,
    SelectionRules,
    apply_daily_selection,
    members_on,
)


@pytest.fixture
def portfolio(db_session):
    row = Portfolio(id=str(uuid.uuid4()), name=f"lifecycle-{uuid.uuid4().hex[:6]}", start_date=date(2026, 1, 1))
    db_session.add(row)
    db_session.commit()
    yield row
    db_session.query(PortfolioStockEvent).filter_by(portfolio_id=row.id).delete()
    db_session.query(PortfolioStock).filter_by(portfolio_id=row.id).delete()
    db_session.delete(row)
    db_session.commit()


def _rankings(codes):
    return [(code, 1.0 - i / 100, i + 1) for i, code in enumerate(codes)]


def test_the_pool_only_decides_eligibility_not_buys(db_session, portfolio):
    """A ranked stock enters as `watching`; the pool is not a basket of positions."""
    result = apply_daily_selection(
        db_session,
        portfolio_id=portfolio.id,
        trade_date=date(2026, 9, 1),
        rankings=_rankings(["A", "B", "C"]),
        rules=SelectionRules(top_n=3, buy_rank_limit=0, sell_rank_limit=100),
    )
    assert result.added == ["A", "B", "C"] and result.bought == []

    rows = db_session.scalars(select(PortfolioStock).where(PortfolioStock.portfolio_id == portfolio.id)).all()
    assert {r.status for r in rows} == {"watching"}
    assert all(r.joined_at == date(2026, 9, 1) for r in rows)


def test_the_buy_rule_promotes_a_ranked_watcher(db_session, portfolio):
    """Default rules buy the same day a stock ranks inside the buy limit."""
    rules = SelectionRules(top_n=3)
    first = apply_daily_selection(
        db_session, portfolio_id=portfolio.id, trade_date=date(2026, 9, 1),
        rankings=_rankings(["A", "B", "C"]), rules=rules,
    )
    assert sorted(first.bought) == ["A", "B", "C"]

    events = db_session.scalars(
        select(PortfolioStockEvent).where(PortfolioStockEvent.event == "bought")
    ).all()
    assert {e.to_status for e in events} == {"holding"}
    assert {e.rule for e in events} == {"buy_rank"}


def test_a_holding_that_leaves_the_pool_is_kept_until_the_sell_limit(db_session, portfolio):
    """Sliding out of the top N is not a sell signal — that is the whole point of two layers."""
    rules = SelectionRules(top_n=2, buy_rank_limit=2, sell_rank_limit=4)
    apply_daily_selection(
        db_session, portfolio_id=portfolio.id, trade_date=date(2026, 9, 1),
        rankings=_rankings(["A", "B"]), rules=rules,
    )
    apply_daily_selection(
        db_session, portfolio_id=portfolio.id, trade_date=date(2026, 9, 2),
        rankings=_rankings(["A", "B"]), rules=rules,
    )  # A and B are now holding

    day3 = apply_daily_selection(
        db_session, portfolio_id=portfolio.id, trade_date=date(2026, 9, 3),
        rankings=_rankings(["C", "D", "A", "B"]), rules=rules,
    )
    assert day3.sold == []            # A/B left the pool but are still within the sell limit
    statuses = {
        r.ts_code: r.status
        for r in db_session.scalars(select(PortfolioStock).where(PortfolioStock.portfolio_id == portfolio.id))
    }
    assert statuses["A"] == "holding" and statuses["B"] == "holding"

    day4 = apply_daily_selection(
        db_session, portfolio_id=portfolio.id, trade_date=date(2026, 9, 4),
        rankings=_rankings(["C", "D", "E", "F", "A"]), rules=rules,
    )
    assert "A" in day4.sold           # rank 5 > sell_rank_limit 4
    assert "B" in day4.sold           # absent entirely


def test_a_soft_deleted_stock_comes_back_as_a_new_episode(db_session, portfolio):
    rules = SelectionRules(top_n=2, buy_rank_limit=0, sell_rank_limit=100, drop_after_absent_days=2)
    apply_daily_selection(
        db_session, portfolio_id=portfolio.id, trade_date=date(2026, 9, 1),
        rankings=_rankings(["A"]), rules=rules,
    )
    dropped = apply_daily_selection(
        db_session, portfolio_id=portfolio.id, trade_date=date(2026, 9, 5),
        rankings=_rankings(["B"]), rules=rules,
    )
    assert dropped.dropped == ["A"]

    row = db_session.scalars(select(PortfolioStock).where(PortfolioStock.ts_code == "A")).one()
    assert row.status == "dropped" and row.left_at == date(2026, 9, 5)

    again = apply_daily_selection(
        db_session, portfolio_id=portfolio.id, trade_date=date(2026, 9, 8),
        rankings=_rankings(["A", "C"]), rules=rules,
    )
    assert again.resurrected == ["A"]
    db_session.refresh(row)
    # Same row, new episode: the unique key on (portfolio, ts_code) forbids an insert.
    assert row.status == "watching" and row.episode == 2
    assert row.joined_at == date(2026, 9, 8) and row.left_at is None


def test_membership_on_a_past_day_is_a_range_query(db_session, portfolio):
    rules = SelectionRules(top_n=2, buy_rank_limit=0, sell_rank_limit=100, drop_after_absent_days=3)
    apply_daily_selection(
        db_session, portfolio_id=portfolio.id, trade_date=date(2026, 9, 1),
        rankings=_rankings(["A", "B"]), rules=rules,
    )
    apply_daily_selection(
        db_session, portfolio_id=portfolio.id, trade_date=date(2026, 9, 10),
        rankings=_rankings(["C"]), rules=rules,
    )

    assert [r.ts_code for r in members_on(db_session, portfolio.id, date(2026, 9, 1))] == ["A", "B"]
    assert [r.ts_code for r in members_on(db_session, portfolio.id, date(2026, 9, 5))] == ["A", "B"]
    # A and B were dropped on 2026-09-10 (absent ≥ 3 days), so they are no longer members.
    assert [r.ts_code for r in members_on(db_session, portfolio.id, date(2026, 9, 11))] == ["C"]


def test_applying_the_same_day_twice_is_refused(db_session, portfolio):
    """The job is a thread in the API process; a restart must not double-book a day."""
    rules = SelectionRules(top_n=2)
    apply_daily_selection(
        db_session, portfolio_id=portfolio.id, trade_date=date(2026, 9, 1),
        rankings=_rankings(["A", "B"]), rules=rules,
    )
    with pytest.raises(LifecycleError, match="already been applied"):
        apply_daily_selection(
            db_session, portfolio_id=portfolio.id, trade_date=date(2026, 9, 1),
            rankings=_rankings(["A", "B"]), rules=rules,
        )


def test_an_empty_ranking_is_refused_rather_than_clearing_the_pool(db_session, portfolio):
    with pytest.raises(LifecycleError, match="no rankings"):
        apply_daily_selection(
            db_session, portfolio_id=portfolio.id, trade_date=date(2026, 9, 1), rankings=[],
        )


def test_events_carry_the_model_and_the_rule_that_produced_them(db_session, portfolio):
    apply_daily_selection(
        db_session, portfolio_id=portfolio.id, trade_date=date(2026, 9, 1),
        rankings=_rankings(["A"]),
        rules=SelectionRules(top_n=1, buy_rank_limit=0),
        model={"name": "scorecard-5d-relative", "version": 7, "dataset_version": 3},
    )
    event = db_session.scalars(select(PortfolioStockEvent)).one()
    assert event.event == "added"
    assert event.score is not None and event.rank == 1
    assert event.model_name == "scorecard-5d-relative"
    assert event.model_version == 7 and event.dataset_version == 3
    assert event.rule_params["top_n"] == 1


def test_the_members_and_events_endpoints_answer_over_http():
    """A missing `date` import turned these into 500s once; a real request is the regression test."""
    import uuid

    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app, raise_server_exceptions=True)
    login = f"lc{uuid.uuid4().hex[:8]}"
    client.post("/api/auth/register", json={"login": login, "password": "secret123"})
    token = client.post("/api/auth/login", json={"login": login, "password": "secret123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    name = f"lc-{uuid.uuid4().hex[:6]}"
    client.post("/api/portfolios", json={"name": name}, headers=headers)

    members = client.get(f"/api/portfolios/{name}/members?day=2026-09-30", headers=headers)
    assert members.status_code == 200
    assert members.json()["members"] == []          # no history for that day yet

    events = client.get(f"/api/portfolios/{name}/events?day=2026-09-30", headers=headers)
    assert events.status_code == 200 and events.json()["events"] == []
