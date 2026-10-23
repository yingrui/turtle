"""Reading and computing factors.

Two jobs: show what a factor is and what it has produced, and run it over the market panel and
store the result. Computation is explicit — nothing recomputes on read, so a value's date tells
you when someone last ran it (as with graph indexing earlier).
"""

from __future__ import annotations

import math
import uuid
from datetime import date, timedelta
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.core.factor.engine import Panel, evaluate, load_panel, required_fields
from app.models import FactorDefinition, FactorValue


class FactorError(ValueError):
    """A request the factor layer refuses: unknown code, no formula, nothing to compute."""


def _insert_for(db):
    """ON CONFLICT is spelled per dialect; both supported engines have the same shape."""
    name = db.bind.dialect.name if db.bind is not None else "postgresql"
    return sqlite_insert if name == "sqlite" else pg_insert


class FactorService:
    def list_definitions(self, db, *, only_active: bool = True) -> list[dict]:
        """Every factor with its coverage, so the list page needs one query per fact."""
        query = select(FactorDefinition).order_by(FactorDefinition.category, FactorDefinition.code)
        if only_active:
            query = query.where(FactorDefinition.is_active.is_(True))
        definitions = db.scalars(query).all()
        coverage = {
            row.factor_id: row
            for row in db.execute(
                select(
                    FactorValue.factor_id,
                    func.count().label("rows"),
                    func.min(FactorValue.trade_date).label("first_date"),
                    func.max(FactorValue.trade_date).label("last_date"),
                    func.count(func.distinct(FactorValue.ts_code)).label("stocks"),
                ).group_by(FactorValue.factor_id)
            ).all()
        }
        out = []
        for definition in definitions:
            stats = coverage.get(definition.id)
            out.append(
                {
                    "code": definition.code,
                    "name": definition.name,
                    "category": definition.category,
                    "direction": definition.direction,
                    "unit": definition.unit,
                    "logic": definition.logic,
                    "formula": definition.formula,
                    "params": definition.params or {},
                    "lookback_days": definition.lookback_days,
                    "ic_ir": _float(definition.ic_ir),
                    "source_ref": definition.source_ref,
                    "is_computable": bool(definition.formula),
                    "value_count": int(stats.rows) if stats else 0,
                    "stock_count": int(stats.stocks) if stats else 0,
                    "first_date": stats.first_date if stats else None,
                    "last_date": stats.last_date if stats else None,
                }
            )
        return out

    def get_definition(self, db, code: str) -> FactorDefinition:
        definition = db.scalar(select(FactorDefinition).where(FactorDefinition.code == code))
        if not definition:
            raise FactorError(f"unknown factor: {code}")
        return definition

    def get_values(
        self,
        db,
        code: str,
        *,
        ts_code: str | None = None,
        trade_date: date | None = None,
        start: date | None = None,
        end: date | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> dict:
        definition = self.get_definition(db, code)
        query = select(FactorValue).where(FactorValue.factor_id == definition.id)
        if ts_code:
            query = query.where(FactorValue.ts_code == ts_code)
        if trade_date:
            query = query.where(FactorValue.trade_date == trade_date)
        if start:
            query = query.where(FactorValue.trade_date >= start)
        if end:
            query = query.where(FactorValue.trade_date <= end)
        total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = db.scalars(
            query.order_by(FactorValue.trade_date.desc(), FactorValue.ts_code).limit(limit).offset(offset)
        ).all()
        return {
            "code": definition.code,
            "name": definition.name,
            "total": int(total),
            "dates": sorted({row.trade_date for row in rows}, reverse=True)[:2],
            "rows": [
                {
                    "ts_code": row.ts_code,
                    "trade_date": row.trade_date,
                    "value": _float(row.value),
                    "extra": row.extra,
                }
                for row in rows
            ],
        }

    def compute(
        self,
        db,
        code: str,
        *,
        start: date | None = None,
        end: date | None = None,
        log=print,
    ) -> dict:
        """Evaluate the formula over the market panel and upsert the values in the window."""
        definition = self.get_definition(db, code)
        if not definition.formula:
            raise FactorError(
                f"{code} has no formula: its inputs (financial statements, order flow) are not in "
                "this database, so it is a definition only"
            )
        end = end or db.scalar(select(func.max(FactorValue.trade_date))) or date.today()
        start = start or date(end.year, 1, 1)

        # History before the window is what a rolling operator needs; it is not stored.
        lookback = int(definition.lookback_days or 0)
        panel_start = start - timedelta(days=lookback * 2 + 10)
        panel = load_panel(db, required_fields(definition.formula), panel_start, end)
        if not panel.frames:
            raise FactorError(f"no market data between {panel_start} and {end}")
        log(f"Loaded panel {panel.dates[0]}…{panel.dates[-1]} ({len(panel.codes)} stocks)")

        values = evaluate(definition.formula, panel)
        values = values[values.index >= start]
        rows = [
            (definition.id, code_, trade_date, float(value))
            for trade_date, line in values.iterrows()
            for code_, value in line.items()
            if value is not None and math.isfinite(value)
        ]
        if not rows:
            raise FactorError(
                "the formula produced no values in this window (not enough history yet?)"
            )
        written = self._upsert(db, rows)
        return {
            "code": definition.code,
            # ISO strings: the job layer stores this dict as JSON.
            "start": start.isoformat(),
            "end": end.isoformat(),
            "rows_written": written,
            "stocks": len({row[1] for row in rows}),
            "dates": len({row[2] for row in rows}),
        }

    def _upsert(self, db, rows: list[tuple], batch: int = 5000) -> int:
        insert = _insert_for(db)
        for offset in range(0, len(rows), batch):
            chunk = rows[offset : offset + batch]
            statement = insert(FactorValue).values(
                [
                    {
                        "factor_id": factor_id,
                        "ts_code": ts_code,
                        "trade_date": trade_date,
                        "value": value,
                    }
                    for factor_id, ts_code, trade_date, value in chunk
                ]
            )
            db.execute(
                statement.on_conflict_do_update(
                    index_elements=["factor_id", "ts_code", "trade_date"],
                    set_={"value": statement.excluded.value, "updated_at": func.now()},
                )
            )
        db.commit()
        return len(rows)

    def computable_codes(self, db) -> Iterable[str]:
        return db.scalars(
            select(FactorDefinition.code).where(FactorDefinition.formula.isnot(None))
        ).all()


def _float(value) -> float | None:
    return None if value is None else float(value)
