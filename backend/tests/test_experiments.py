"""An experiment without controls cannot be created, and cannot be concluded."""

import pytest

from app.services.experiment_service import ExperimentService


import uuid


def _payload(**overrides):
    base = {
        "id": f"exp-{uuid.uuid4().hex[:8]}",
        "question": "regime switching beats a fixed sign",
        "variants": [{"name": "regime", "ranking_source_id": "regime-ma60-v1"}],
        "controls": [{"name": "random11", "ranking_source_id": "pool-random-11"}],
        "label": {"kind": "benchmark", "horizon": 20},
        "strategy": "pool_entry",
        "window_start": "2025-07-01",
        "window_end": "2026-10-09",
    }
    base.update(overrides)
    return base


def test_an_experiment_without_controls_is_refused(db_session):
    with pytest.raises(ValueError, match="control"):
        ExperimentService().create(db_session, _payload(controls=[]))


def test_the_matrix_lists_variants_then_controls(db_session):
    experiment = ExperimentService().create(db_session, _payload(
        variants=[{"name": "regime"}, {"name": "always-rev"}],
        controls=[{"name": "random11"}, {"name": "random12"}],
    ))
    cells = ExperimentService().cells(experiment)
    assert [name for name, _, _ in cells] == ["regime", "always-rev", "random11", "random12"]
    assert [is_control for _, _, is_control in cells] == [False, False, True, True]


def test_concluding_requires_the_controls_to_have_run(db_session):
    service = ExperimentService()
    experiment = service.create(db_session, _payload())
    with pytest.raises(ValueError, match="control"):
        service.conclude(db_session, experiment, {"verdict": "no incremental information"})


def test_a_conclusion_is_stored_with_its_evidence(db_session):
    service = ExperimentService()
    experiment = service.create(db_session, _payload())
    service.attach(db_session, experiment.id, "random11", run_id="run-1", is_control=True)
    concluded = service.conclude(
        db_session, experiment, {"verdict": "no incremental information", "evidence": "+0.3σ"}
    )
    assert concluded.status == "concluded"
    assert concluded.conclusion["evidence"] == "+0.3σ"


def test_the_summary_measures_each_variant_against_the_control_spread(db_session):
    service = ExperimentService()
    experiment = service.create(db_session, _payload(
        variants=[{"name": "regime"}],
        controls=[{"name": "random11"}, {"name": "random12"}, {"name": "random13"}],
    ))
    from datetime import datetime

    from app.models.simulation import SimulationRun

    for name, excess, control in (("regime", 9.0, False), ("random11", 1.0, True),
                                  ("random12", 5.0, True), ("random13", -3.0, True)):
        run = SimulationRun(
            id=f"run-{name}", portfolio_name="p", policy_id=0, config_snapshot="{}",
            return_rate_pct=excess, finished_at=datetime(2026, 10, 1),
        )
        db_session.add(run)
        db_session.commit()
        service.attach(db_session, experiment.id, name, run_id=run.id, is_control=control)

    summary = service.summary(db_session, experiment)
    assert summary["controls"]["n"] == 3
    regime = next(cell for cell in summary["cells"] if cell["variant"] == "regime")
    assert regime["sigma"] == 2.0      # mean 1.0, sd 4.0 → (9 − 1) / 4


def test_expanding_creates_one_job_per_cell_and_remembers_them(db_session):
    """The matrix is the point: variants and controls must run under the same window and strategy."""
    import json

    from app.models.job import Job

    service = ExperimentService()
    experiment = service.create(db_session, _payload(
        variants=[{"name": "regime", "ranking_source_id": "regime-ma60-v1"}],
        controls=[{"name": "random11", "ranking_source_id": "pool-random-11"}],
    ))
    launched = service.expand(db_session, experiment)

    assert [cell["variant"] for cell in launched] == ["regime", "random11"]
    assert launched[0]["is_control"] is False and launched[1]["is_control"] is True
    assert experiment.status == "running"
    jobs = db_session.query(Job).all()
    assert len(jobs) == 2
    payload = json.loads(jobs[0].payload)
    assert payload["ranking_source_id"] == "regime-ma60-v1"
    assert payload["start_date"] == "2025-07-01" and payload["buy_rule"] == "pool_entry"

    from app.models.experiment import ExperimentRun

    cells = db_session.query(ExperimentRun).filter(ExperimentRun.experiment_id == experiment.id).all()
    assert {cell.variant for cell in cells} == {"regime", "random11"}
    assert all(cell.job_id for cell in cells)

    # Leave the global job table as we found it: another test asserts what a restart does to *all* jobs.
    db_session.query(Job).delete()
    db_session.commit()


def test_expanding_refuses_a_cell_without_a_source(db_session):
    service = ExperimentService()
    experiment = service.create(db_session, _payload(
        variants=[{"name": "broken"}], controls=[{"name": "random11", "ranking_source_id": "x"}]
    ))
    with pytest.raises(ValueError, match="missing a ranking source"):
        service.expand(db_session, experiment)
