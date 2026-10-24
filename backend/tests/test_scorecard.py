"""The scorecard's arithmetic: forward returns, WOE/IV, AUC, and the ridge fit.

These are the parts that decide whether a top-N list means anything, so they are tested directly
rather than through the script's output.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def _prices() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=8, freq="D").date
    rows = []
    for code, offset in (("A", 0.0), ("B", 100.0)):
        for i, day in enumerate(dates):
            rows.append(
                {
                    "ts_code": code,
                    "trade_date": day,
                    "open": offset + 10.0 + i,
                    "close": offset + 10.5 + i,
                }
            )
    return pd.DataFrame(rows)


def test_forward_returns_enter_next_open_and_exit_horizon_later():
    from scripts.scorecard import forward_returns

    frame = forward_returns(_prices(), horizon=5).set_index(["ts_code", "trade_date"])
    days = sorted(frame.loc["A"].index)

    # Signal on day 0: buy day 1's open (11.0), sell day 5's close (10.5 + 5 = 15.5).
    assert frame.loc[("A", days[0]), "fwd_ret"] == pytest.approx(15.5 / 11.0 - 1)
    # The last horizons have no exit price, so no label rather than a wrong one.
    assert frame.loc[("A", days[-1]), "fwd_ret"] != frame.loc[("A", days[-1]), "fwd_ret"]


def test_woe_grows_when_the_top_decile_outperforms():
    from scripts.scorecard import woe_table

    ranks = pd.Series(np.linspace(0.005, 0.995, 1000))
    labels = pd.Series((ranks > 0.5).astype(int).to_numpy())    # every good one is in the top half

    table = woe_table(ranks, labels)
    assert table.loc[0, "woe"] < 0 < table.loc[9, "woe"]
    assert table["iv"].sum() > 0
    assert table.loc[9, "good_rate"] == pytest.approx(1.0)
    assert table.loc[0, "good_rate"] == pytest.approx(0.0)


def test_woe_handles_a_bin_with_no_positives():
    from scripts.scorecard import woe_table

    ranks = pd.Series(np.linspace(0.005, 0.995, 200))
    labels = pd.Series([0] * 199 + [1])                        # one good, in the last decile

    table = woe_table(ranks, labels)
    assert np.isfinite(table["woe"]).all()                     # the 0.5 smoothing keeps it finite
    assert table["iv"].sum() > 0


def test_auc_is_one_for_perfect_order_and_half_for_a_coin_flip():
    from scripts.scorecard import auc

    labels = np.array([0, 0, 1, 1])
    assert auc(np.array([0.1, 0.2, 0.8, 0.9]), labels) == pytest.approx(1.0)
    assert auc(np.array([0.9, 0.8, 0.2, 0.1]), labels) == pytest.approx(0.0)
    assert auc(np.array([0.5, 0.5, 0.5, 0.5]), labels) == pytest.approx(0.5)


def test_fit_recovers_a_signal_and_stays_finite_when_separable():
    from scripts.scorecard import fit_logit

    rng = np.random.default_rng(0)
    x = rng.normal(size=(2000, 2))
    logits = 1.5 * x[:, 0] - 2.0 * x[:, 1]
    y = (rng.random(2000) < 1 / (1 + np.exp(-logits))).astype(int)

    design = np.column_stack([np.ones(2000), x])
    beta = fit_logit(design, y)
    assert beta[1] == pytest.approx(1.5, abs=0.4)
    assert beta[2] == pytest.approx(-2.0, abs=0.4)

    # Perfectly separable data drives an unpenalised fit to infinity; the ridge keeps it bounded.
    separable = np.column_stack([np.ones(200), np.linspace(-3, 3, 200)])
    labels = (separable[:, 1] > 0).astype(int)
    assert np.isfinite(fit_logit(separable, labels)).all()


def test_score_frame_is_the_sum_of_coefficient_times_woe():
    from scripts.scorecard import score_frame

    model = {
        "intercept": 0.1,
        "bins": 10,
        "factors": [{"code": "mom", "coef": 0.5, "woe": [-2.0] * 5 + [2.0] * 5}],
    }
    ranks = pd.DataFrame({"mom": [0.05, 0.95, None]})       # missing → neutral rank
    scores = score_frame(model, ranks)

    assert scores[0] == pytest.approx(0.1 + 0.5 * -2.0)
    assert scores[1] == pytest.approx(0.1 + 0.5 * 2.0)
    assert scores[2] == pytest.approx(0.1 + 0.5 * 2.0)      # neutral rank lands in the upper half
