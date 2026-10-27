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
