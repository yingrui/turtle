"""The model-driven run: configuration guards, model resolution, and scoring."""

from __future__ import annotations

import json
from datetime import date

import pandas as pd
import pytest


def test_a_sell_limit_below_the_pool_is_refused():
    """Selling at a tighter rank than the buy rank would sell what it just bought."""
    from app.core.simulation.model_runner import ModelRunConfig

    with pytest.raises(ValueError, match="sell_rank_limit"):
        ModelRunConfig(top_n=50, sell_rank_limit=10)
    with pytest.raises(ValueError, match="top_n"):
        ModelRunConfig(top_n=0)
    config = ModelRunConfig(top_n=50)
    assert config.sell_rank_limit == 100


def test_the_config_is_recorded_in_full():
    """Every knob that changes the outcome travels with the run, or the run is not reproducible."""
    from app.core.simulation.model_runner import ModelRunConfig

    recorded = ModelRunConfig(top_n=20, cash_buffer=0.1, max_holding_days=30).as_dict()
    assert recorded["top_n"] == 20 and recorded["sell_rank_limit"] == 40
    assert recorded["cash_buffer"] == 0.1 and recorded["max_holding_days"] == 30


def test_a_month_without_a_model_falls_back_to_the_latest_earlier_one(tmp_path):
    """Never forward in time: a model that has seen the future cannot score the past."""
    from app.core.factor.score import model_path_for

    root = tmp_path
    (root / "expanding").mkdir()
    feb = root / "expanding" / "2026-02.json"
    feb.write_text(json.dumps({"intercept": 0, "bins": 10, "factors": []}))
    (root / "expanding" / "index.json").write_text(
        json.dumps(
            {
                "2026-02": {"model_path": str(feb)},
                "2026-03": {"skipped": "no factor reached IV >= 0.02"},
            }
        )
    )

    assert model_path_for(date(2026, 2, 10), "expanding", root) == feb
    # March has no model → February's is used; January has nothing earlier.
    assert model_path_for(date(2026, 3, 15), "expanding", root) == feb
    with pytest.raises(Exception, match="no model trained"):
        model_path_for(date(2026, 1, 15), "expanding", root)


def test_scoring_ignores_a_factor_the_model_knows_but_the_panel_lacks():
    """A missing column scores neutral; it must not crash a run that would otherwise be fine."""
    from app.core.factor.score import score_frame

    model = {
        "intercept": 0.1,
        "bins": 10,
        "factors": [
            {"code": "mom", "coef": 0.5, "woe": [-2.0] * 5 + [2.0] * 5},
            {"code": "gone", "coef": 9.9, "woe": [0.0] * 10},
        ],
    }
    ranks = pd.DataFrame({"mom": [0.05, 0.95]})
    scores = score_frame(model, ranks)
    assert scores[0] == pytest.approx(0.1 - 1.0)
    assert scores[1] == pytest.approx(0.1 + 1.0)


def test_the_pool_is_recorded_per_day_and_readable_by_date():
    """A dynamic pool has no history in today's state — it is written with the run, day by day."""
    import uuid as _uuid

    from app.core.simulation.model_runner import pool_dates, pool_on
    from app.database import SessionLocal
    from app.models import Portfolio
    from app.models.simulation import SimulationPool, SimulationRun

    db = SessionLocal()
    try:
        portfolio = Portfolio(id=str(_uuid.uuid4()), name=f"pool-{_uuid.uuid4().hex[:6]}", balance=0)
        run = SimulationRun(
            id=str(_uuid.uuid4()),
            portfolio_name=portfolio.name,
            policy_id=0,
            mode="model",
            pool_mode="dynamic",
            config_snapshot="{}",
        )
        db.add_all([portfolio, run])
        db.commit()
        for day, codes in ((date(2026, 5, 14), ["A", "B"]), (date(2026, 5, 15), ["C"])):
            for rank, code in enumerate(codes, start=1):
                db.add(
                    SimulationPool(
                        run_id=run.id, trade_date=day, ts_code=code, rank=rank, score=0.5,
                        held=rank == 1,
                    )
                )
        db.commit()

        assert pool_dates(db, run.id) == [date(2026, 5, 14), date(2026, 5, 15)]
        first = pool_on(db, run.id, date(2026, 5, 14))
        assert [row.ts_code for row in first] == ["A", "B"]
        assert first[0].held is True and first[1].held is False

        db.delete(db.get(SimulationRun, run.id))
        db.delete(db.get(Portfolio, portfolio.id))
        db.commit()
    finally:
        db.close()


def test_a_fixed_pool_needs_no_rows():
    """A fixed pool is the configured list: storing it per day would duplicate it thousands of times."""
    from app.models.simulation import SimulationRun

    # The model's default, not the DB's: a run that never sets it is a fixed-pool run.
    assert SimulationRun.__table__.c.pool_mode.server_default.arg == "fixed"


def test_a_bound_run_supplies_the_portfolios_stocks_and_trades():
    """`/stocks` and `/transactions` follow the bound run instead of the editable book."""
    import uuid as _uuid
    from decimal import Decimal

    from app.database import SessionLocal
    from app.models import Portfolio
    from app.models.simulation import SimulationHolding, SimulationRun, SimulationTrade

    db = SessionLocal()
    try:
        portfolio = Portfolio(
            id=str(_uuid.uuid4()), name=f"bound-{_uuid.uuid4().hex[:6]}", balance=Decimal("0")
        )
        run = SimulationRun(
            id=str(_uuid.uuid4()), portfolio_name=portfolio.name, portfolio_id=portfolio.id,
            policy_id=0, mode="model", pool_mode="dynamic", config_snapshot="{}",
        )
        portfolio.active_run_id = run.id
        db.add_all([portfolio, run])
        db.commit()
        db.add_all(
            [
                SimulationHolding(
                    run_id=run.id, trade_date=date(2026, 5, 14), ts_code="600519.SH", shares=100,
                    price=Decimal("10"), market_value=Decimal("1000"), weight=Decimal("0.5"),
                    rank=3, score=Decimal("0.4"),
                ),
                SimulationTrade(
                    id=str(_uuid.uuid4()), run_id=run.id, ts_code="600519.SH",
                    trade_date=date(2026, 5, 14), side="buy", shares=100, price=Decimal("10"),
                    amount=Decimal("1000"), reason="in_top_n",
                ),
            ]
        )
        db.commit()

        from app.api.portfolios import _run_stock_view, _run_trade_view

        stocks = _run_stock_view(db, portfolio.id, None)
        assert stocks["source"] == "run" and stocks["trade_date"] == "2026-05-14"
        assert stocks["stocks"][0]["ts_code"] == "600519.SH"
        assert stocks["stocks"][0]["status"] == "holding"

        trades = _run_trade_view(db, portfolio.id, ts_code=None, limit=10, offset=0)
        assert trades["source"] == "run" and trades["transactions"][0]["side"] == "buy"

        # Unbinding returns the portfolio to its own (empty) book.
        portfolio.active_run_id = None
        db.commit()
        assert _run_stock_view(db, portfolio.id, None) is None

        db.delete(db.get(SimulationRun, run.id))
        db.delete(db.get(Portfolio, portfolio.id))
        db.commit()
    finally:
        db.close()


def test_the_runner_trades_a_ranking_it_knows_nothing_about():
    """Decoupling: any ordered list works — the simulation imports no model, label or dataset."""
    import uuid as _uuid
    from decimal import Decimal

    from sqlalchemy import text

    from app.core.simulation.model_runner import ModelRunConfig, run_model_simulation
    from app.core.simulation.ranking import StaticRankingProvider
    from app.core.tushare_schema import tushare_table
    from app.database import SessionLocal
    from app.models import Portfolio
    from app.models.simulation import SimulationHolding, SimulationPool, SimulationRun, SimulationTrade

    db = SessionLocal()
    try:
        # A two-name "market" for one session, so the runner has prices to trade on.
        table = tushare_table("stock_trade_daily")
        # Two sessions: the signal is computed on the first close and filled at the **second open**,
        # which is what the runner does now.
        for day, close, open_price in (
            (date(2026, 5, 14), 10.0, 10.0),
            (date(2026, 5, 15), 11.0, 10.5),
        ):
            for code, price in (("600519.SH", close), ("000001.SZ", close)):
                db.execute(
                    text(
                        f"INSERT INTO {table} (ts_code, trade_date, open, high, low, close, pre_close, vol) "
                        "VALUES (:code, :day, :open, :close, :close, :close, :close, 1000)"
                    ),
                    {"code": code, "day": day, "open": open_price, "close": price},
                )

        portfolio = Portfolio(
            id=str(_uuid.uuid4()), name=f"rank-{_uuid.uuid4().hex[:6]}", balance=Decimal("0")
        )
        run = SimulationRun(
            id=str(_uuid.uuid4()), portfolio_name=portfolio.name, portfolio_id=portfolio.id,
            policy_id=0, mode="model", pool_mode="dynamic", config_snapshot="{}",
        )
        db.add_all([portfolio, run])
        db.commit()

        provider = StaticRankingProvider(["600519.SH", "000001.SZ"])
        result = run_model_simulation(
            db, run=run, start=date(2026, 5, 14), end=date(2026, 5, 14),
            initial_cash=1_000_000, config=ModelRunConfig(top_n=2), provider=provider,
        )
        db.commit()

        assert result.days == 1 and result.trades == 2
        # Filled at 05-15's open, not at the 05-14 close that produced the ranking.
        trade = db.query(SimulationTrade).filter_by(run_id=run.id).first()
        assert float(trade.price) == pytest.approx(10.5)
        assert db.query(SimulationPool).filter_by(run_id=run.id).count() == 2
        assert db.query(SimulationHolding).filter_by(run_id=run.id).count() == 2

        db.query(SimulationHolding).filter_by(run_id=run.id).delete()
        db.query(SimulationPool).filter_by(run_id=run.id).delete()
        db.query(SimulationTrade).filter_by(run_id=run.id).delete()
        db.execute(
            text(f"DELETE FROM {table} WHERE trade_date IN (:d1, :d2)"),
            {"d1": date(2026, 5, 14), "d2": date(2026, 5, 15)},
        )
        db.delete(db.get(SimulationRun, run.id))
        db.delete(db.get(Portfolio, portfolio.id))
        db.commit()
    finally:
        db.close()
