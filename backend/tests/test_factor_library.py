"""The factor library is two tables: what a factor means, and its panel of values."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError


@pytest.fixture(autouse=True)
def _clean(db_session):
    """The sqlite file is shared for the session; start and end every test empty."""
    from app.models import FactorDefinition, FactorValue

    db_session.execute(delete(FactorValue))
    db_session.execute(delete(FactorDefinition))
    db_session.commit()
    yield
    db_session.execute(delete(FactorValue))
    db_session.execute(delete(FactorDefinition))
    db_session.commit()


def _definition(**overrides):
    from app.models import FactorDefinition

    payload = {
        "id": str(uuid.uuid4()),
        "code": f"mom_20d_{uuid.uuid4().hex[:8]}",
        "name": "20日动量",
        "category": "price-volume",
        "direction": "positive",
        "logic": "close / close[-20] - 1",
        "params": {"window": 20},
        "lookback_days": 20,
    }
    payload.update(overrides)
    return FactorDefinition(**payload)


def test_a_factor_is_identified_by_its_code(db_session):
    code = f"dup_{uuid.uuid4().hex[:8]}"
    db_session.add(_definition(code=code))
    db_session.commit()

    with pytest.raises(IntegrityError):
        db_session.add(_definition(code=code, name="重名的另一个动量因子"))
        db_session.commit()
    db_session.rollback()


def test_recomputing_a_day_overwrites_the_same_key(db_session):
    from app.models import FactorValue

    factor = _definition()
    db_session.add(factor)
    db_session.commit()

    def write(value):
        stmt = sqlite_insert(FactorValue).values(
            factor_id=factor.id, ts_code="600519.SH", trade_date=date(2024, 5, 6), value=value
        )
        db_session.execute(
            stmt.on_conflict_do_update(
                index_elements=["factor_id", "ts_code", "trade_date"],
                set_={"value": stmt.excluded.value},
            )
        )
        db_session.commit()

    write(0.031)
    write(0.042)

    rows = db_session.scalars(
        select(FactorValue).where(FactorValue.factor_id == factor.id)
    ).all()
    assert len(rows) == 1 and float(rows[0].value) == pytest.approx(0.042)


def test_deleting_a_factor_takes_its_values_with_it(db_session):
    from app.models import FactorValue

    factor = _definition(name="60日波动率")
    db_session.add(factor)
    db_session.commit()
    db_session.add(
        FactorValue(
            factor_id=factor.id, ts_code="000001.SZ", trade_date=date(2024, 5, 6), value=0.21
        )
    )
    db_session.commit()

    db_session.delete(factor)
    db_session.commit()

    assert db_session.scalars(select(FactorValue)).all() == []


def test_a_cross_section_reads_one_factor_for_one_day(db_session):
    from app.models import FactorValue

    mom = _definition()
    vol = _definition(name="60日波动率")
    db_session.add_all([mom, vol])
    db_session.commit()

    day = date(2024, 5, 6)
    db_session.add_all(
        [
            FactorValue(factor_id=mom.id, ts_code="600519.SH", trade_date=day, value=0.031),
            FactorValue(factor_id=mom.id, ts_code="000001.SZ", trade_date=day, value=-0.012),
            FactorValue(
                factor_id=mom.id, ts_code="600519.SH", trade_date=date(2024, 5, 3), value=0.02
            ),
            FactorValue(factor_id=vol.id, ts_code="600519.SH", trade_date=day, value=0.19),
        ]
    )
    db_session.commit()

    rows = db_session.scalars(
        select(FactorValue).where(FactorValue.factor_id == mom.id, FactorValue.trade_date == day)
    ).all()
    assert {r.ts_code for r in rows} == {"600519.SH", "000001.SZ"}


def test_coverage_is_a_column_so_the_catalogue_never_aggregates(db_session):
    from app.models import FactorValue
    from app.services.factor_service import FactorService

    factor = _definition()
    db_session.add(factor)
    db_session.commit()
    day = date(2024, 5, 6)
    db_session.add_all(
        [
            FactorValue(factor_id=factor.id, ts_code="600519.SH", trade_date=day, value=0.03),
            FactorValue(
                factor_id=factor.id, ts_code="600519.SH", trade_date=date(2024, 5, 7), value=0.04
            ),
            FactorValue(factor_id=factor.id, ts_code="000001.SZ", trade_date=day, value=-0.01),
        ]
    )
    db_session.commit()

    service = FactorService()
    # Before a compute has recorded anything, the catalogue says zero rather than aggregating.
    assert {f["code"]: f for f in service.list_definitions(db_session)}[factor.code][
        "value_count"
    ] == 0

    service.refresh_coverage(db_session, factor)
    row = {f["code"]: f for f in service.list_definitions(db_session)}[factor.code]
    assert row["value_count"] == 3
    assert row["stock_count"] == 2
    assert row["first_date"] == day
    assert row["last_date"] == date(2024, 5, 7)
    assert row["computed_at"] is not None


def test_a_restart_closes_the_jobs_it_killed(db_session):
    """A job is a thread in the API process; a restart abandons it, so the row must not say running."""
    import json

    from app.models import Job
    from app.services.job_service import JobService

    stale = Job(id="job-stale", type="factor_compute", status="running", payload=json.dumps({}))
    queued = Job(id="job-queued", type="factor_compute", status="pending", payload=json.dumps({}))
    done = Job(id="job-done", type="factor_compute", status="completed", payload=json.dumps({}))
    db_session.add_all([stale, queued, done])
    db_session.commit()

    assert JobService().mark_interrupted(db_session) == 2
    assert stale.status == "failed" and "restart" in (stale.error or "")
    assert queued.status == "failed"
    assert done.status == "completed"          # finished work is left alone
