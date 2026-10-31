"""Methods are registered with a contract the UI and the validator both read."""

from app.analysis import methods, registry
from app.analysis.artifact import ScoreTable


def test_every_method_declares_params_and_output():
    specs = registry.all_methods()
    assert {spec.name for spec in specs} >= {"regime_score", "constant_pool"}
    for spec in specs:
        assert spec.params_model.model_json_schema().get("properties") is not None
        assert spec.output_kind in {"score_table", "model"}
        assert spec.display_name, spec.name


def test_regime_score_declares_the_factors_it_consumes():
    """The factor list is a contract: a model cached against it must invalidate if it changes."""
    assert set(registry.get("regime_score").needs_factors) == {"mom_20d", "MACD", "ma_dev_20"}


def test_the_describe_payload_is_enough_to_render_a_form():
    described = registry.describe()
    regime = next(item for item in described if item["name"] == "regime_score")
    properties = regime["params_schema"]["properties"]
    assert {"start", "end", "ma_window", "horizon"} <= set(properties)
    assert properties["ma_window"]["default"] == 60


def test_unknown_method_is_rejected():
    try:
        registry.get("no_such_method")
    except KeyError as exc:
        assert "unknown analysis method" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected KeyError")


def test_validation_reports_schema_and_key_problems():
    import pandas as pd

    from app.services.analysis_service import validate

    spec = registry.get("regime_score")
    good = ScoreTable(frame=pd.DataFrame([{"trade_date": "2026-05-14", "ts_code": "600519.SH", "score": 1.0}]))
    assert validate(good, spec)["ok"] is True

    duplicated = ScoreTable(
        frame=pd.DataFrame(
            [
                {"trade_date": "2026-05-14", "ts_code": "600519.SH", "score": 1.0},
                {"trade_date": "2026-05-14", "ts_code": "600519.SH", "score": 2.0},
            ]
        )
    )
    report = validate(duplicated, spec)
    assert report["ok"] is False
    assert any(check["gate"] == "unique_keys" and not check["ok"] for check in report["checks"])


def test_control_helpers_are_not_offered_as_analyses():
    """A basket with no model behind it is a benchmark, not a cross-sectional analysis."""
    described = {item["name"]: item for item in registry.describe()}
    assert described["constant_pool"]["family"] == "control"
    assert described["regime_score"]["family"] == "analysis"


def test_the_api_exposes_the_family_so_the_page_can_filter():
    payload = registry.describe()
    assert all("family" in item for item in payload)
