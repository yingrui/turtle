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
