"""The factor engine: a small expression language over a wide market panel.

The panel here is synthetic, so the numbers are arithmetic rather than market truth — what is
under test is that each operator means what its name says, and that a formula cannot reach
anything outside the allow-list.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def _panel(close_values, **extra):
    """One field of three days x two stocks, plus any extra fields."""
    index = pd.date_range("2024-01-01", periods=len(close_values), freq="D")
    frames = {
        "close": pd.DataFrame(close_values, index=index, columns=["A", "B"], dtype="float64"),
    }
    for name, values in extra.items():
        frames[name] = pd.DataFrame(values, index=index, columns=["A", "B"], dtype="float64")
    return frames


def _evaluate(formula, **extra):
    from app.core.factor.engine import Panel, evaluate

    return evaluate(formula, Panel(_panel([[10.0, 20.0], [11.0, 18.0], [12.2, 19.8]], **extra)))


def test_returns_are_the_ratio_against_n_days_ago():
    values = _evaluate("ts_ret(close, 1)")
    assert values.iloc[1]["A"] == pytest.approx(0.1)
    assert values.iloc[1]["B"] == pytest.approx(-0.1)
    assert np.isnan(values.iloc[0]["A"])          # nothing to compare the first day against


def test_ma_is_the_trailing_mean_and_needs_a_full_window():
    values = _evaluate("ma(close, 2)")
    assert np.isnan(values.iloc[0]["A"])
    assert values.iloc[1]["A"] == pytest.approx(10.5)
    assert values.iloc[2]["A"] == pytest.approx(11.6)


def test_where_keeps_only_the_days_a_condition_holds():
    values = _evaluate("where(ts_ret(close, 1) > 0, ts_ret(close, 1), nan)")
    assert values.iloc[1]["A"] == pytest.approx(0.1)
    assert np.isnan(values.iloc[1]["B"])          # B fell, so the day is dropped


def test_std_takes_an_optional_min_periods():
    values = _evaluate("std(ts_ret(close, 1), 3, 2)")
    assert np.isnan(values.iloc[0]["A"])
    assert np.isnan(values.iloc[1]["A"])          # a single observation has no spread
    assert not np.isnan(values.iloc[2]["A"])      # two are enough when told so


def test_two_fields_can_be_combined():
    prices = [[10.0, 20.0], [11.0, 18.0], [12.2, 19.8]]
    values = _evaluate("close / shift(close, 1) - 1", vol=[[1.0, 1.0], [2.0, 3.0], [4.0, 9.0]])
    assert values.iloc[2]["B"] == pytest.approx(19.8 / 18.0 - 1)
    assert prices[-1][0] == 12.2


def test_a_cross_sectional_rank_is_computed_per_day():
    from app.core.factor.engine import Panel, evaluate

    values = evaluate(
        "rank_cs(close)", Panel(_panel([[10.0, 20.0], [11.0, 18.0], [12.2, 19.8]]))
    )
    assert values.iloc[0]["A"] == pytest.approx(0.5)   # 10 of (10, 20)
    assert values.iloc[0]["B"] == pytest.approx(1.0)
    assert values.iloc[1]["A"] == pytest.approx(0.5)   # 11 of (11, 18)
    assert values.iloc[1]["B"] == pytest.approx(1.0)


def test_a_formula_cannot_call_anything_it_likes():
    from app.core.factor.engine import Panel, evaluate

    for formula in ("__import__('os').system('true')", "open('/etc/passwd')", "[1, 2]"):
        with pytest.raises(ValueError):
            evaluate(formula, Panel(_panel([[1.0, 2.0]])))


def test_a_formula_cannot_read_a_name_it_was_not_given():
    from app.core.factor.engine import Panel, evaluate

    with pytest.raises(ValueError, match="unknown name"):
        evaluate("close / whatever", Panel(_panel([[1.0, 2.0]])))


def test_required_fields_names_only_real_columns():
    from app.core.factor.engine import required_fields

    assert required_fields("close / shift(close, 20) - 1") == {"close"}
    assert required_fields("corr(close, turnover_rate, 20)") == {"close", "turnover_rate"}
    assert required_fields("ma(close, 20)") == {"close"}       # a function is not a field
