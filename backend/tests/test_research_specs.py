"""Factors, labels and strategies are declared objects with contracts."""

from datetime import date

from app.core.simulation import strategies
from app.models.model_artifact import fingerprint
from app.models.research import FactorSpec, Label


def test_labels_render_their_own_provenance():
    label = Label(id="bench20", kind="benchmark", horizon=20, benchmark="000300.SH")
    assert label.as_provenance() == {
        "id": "bench20", "kind": "benchmark", "horizon": 20, "benchmark": "000300.SH",
    }


def test_label_entry_and_exit_are_explicit():
    """A label that does not say when it enters and exits cannot be compared with another one."""
    label = Label(id="bench20", kind="benchmark")
    # `default=` applies at flush time, so read the declaration rather than an unflushed instance.
    assert Label.__table__.c.entry.default.arg == "open[t+1]"
    assert Label.__table__.c.exit.default.arg == "close[t+1+h]"


def test_a_factor_carries_its_dependencies_and_pit_rule():
    spec = FactorSpec(
        code="n_income_yoy", version=1, needs=[{"table": "income", "column": "n_income", "as_of": "ann_date"}],
        pit={"lag_days": 1}, category="fundamental",
    )
    assert spec.needs[0]["as_of"] == "ann_date"
    assert spec.version == 1


def test_factor_version_participates_in_the_model_fingerprint():
    base = dict(method="scorecard_train", period="2025-07", period_kind="month", params={},
                label={"kind": "benchmark"}, dataset={"name": "d", "version": 1})
    v1 = fingerprint(factors=[{"code": "mom_20d", "version": 1}], **base)
    v2 = fingerprint(factors=[{"code": "mom_20d", "version": 2}], **base)
    assert v1 != v2


def test_every_strategy_declares_a_parameter_schema():
    described = strategies.describe()
    assert {item["name"] for item in described} == {"policy", "pool_entry", "mechanical"}
    for item in described:
        assert item["params_schema"]["properties"], item["name"]


def test_pool_entry_is_the_strategy_that_fits_a_rotating_pool():
    spec = strategies.get("pool_entry")
    assert spec.enter_on_pool is True
    assert strategies.get("policy").enter_on_pool is False


def test_unknown_strategy_is_rejected():
    try:
        strategies.get("nope")
    except KeyError as exc:
        assert "unknown strategy" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected KeyError")
