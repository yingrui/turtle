"""Training is skipped only when the cached model is the same model.

The fingerprint is the whole contract: same inputs → skip; any difference → train again.
"""

from datetime import date

from app.models.model_artifact import ModelArtifact, fingerprint
from app.services.model_artifact_service import ModelArtifactService, ModelUnavailable, period_of

FACTORS = [{"code": "mom_20d", "version": 1}, {"code": "MACD", "version": 1}]
LABEL = {"kind": "benchmark", "horizon": 20, "benchmark": "000300.SH"}
DATASET = {"name": "scorecard-training-20d-bench", "version": 2, "manifest_sha256": "dfb1524b"}
PARAMS = {"bins": 10, "alpha": 1.0}


def _fingerprint(**overrides):
    base = dict(
        method="scorecard_train", period="2025-07", period_kind="month",
        params=PARAMS, factors=FACTORS, label=LABEL, dataset=DATASET,
    )
    base.update(overrides)
    return fingerprint(**base)


def test_periods_are_labeled_by_month_or_week():
    assert period_of(date(2025, 7, 3), "month") == "2025-07"
    assert period_of(date(2025, 7, 3), "week").startswith("2025-W")


def test_same_inputs_give_the_same_fingerprint():
    assert _fingerprint() == _fingerprint()


def test_a_new_dataset_version_invalidates_the_cache():
    other = {**DATASET, "version": 3}
    assert _fingerprint(dataset=other) != _fingerprint()


def test_a_factor_version_bump_invalidates_the_cache():
    """Otherwise a changed formula keeps serving a model trained on the old inputs."""
    bumped = [{"code": "mom_20d", "version": 2}, {"code": "MACD", "version": 1}]
    assert _fingerprint(factors=bumped) != _fingerprint()


def test_hyperparameters_and_label_take_part():
    assert _fingerprint(params={**PARAMS, "bins": 20}) != _fingerprint()
    assert _fingerprint(label={**LABEL, "horizon": 5}) != _fingerprint()


def test_a_cached_model_is_reused_without_training(db_session):
    service = ModelArtifactService(db_session)
    trained = []

    def train(key):
        trained.append(key)
        return ModelArtifact(
            fingerprint=key, method="scorecard_train", period="2025-07", period_kind="month",
            artifact_key="k", artifact_sha256="s",
        )

    first, outcome = service.resolve(
        period="2025-07", period_kind="month", method="scorecard_train", params=PARAMS,
        factors=FACTORS, label=LABEL, dataset=DATASET, retrain="monthly", train=train,
    )
    second, outcome2 = service.resolve(
        period="2025-07", period_kind="month", method="scorecard_train", params=PARAMS,
        factors=FACTORS, label=LABEL, dataset=DATASET, retrain="monthly", train=train,
    )

    assert outcome == "trained" and outcome2 == "hit"
    assert len(trained) == 1, "the second resolve must not retrain"
    assert first.fingerprint == second.fingerprint


def test_retrain_none_refuses_to_train_a_missing_model(db_session):
    service = ModelArtifactService(db_session)
    try:
        service.resolve(
            period="2025-08", period_kind="month", method="scorecard_train", params=PARAMS,
            factors=FACTORS, label=LABEL, dataset=DATASET, retrain="none",
            train=lambda key: None,
        )
    except ModelUnavailable as exc:
        assert "retrain=none" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ModelUnavailable")
