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
