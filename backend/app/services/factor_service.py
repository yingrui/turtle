"""Reading and computing factors.

Two jobs: show what a factor is and what it has produced, and run it over the market panel and
store the result. Computation is explicit — nothing recomputes on read, so a value's date tells
you when someone last ran it (as with graph indexing earlier).
"""

from __future__ import annotations

import math
import uuid
from datetime import date, datetime, timedelta
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
        """Every factor with the coverage of its last compute — a 47-row read, not an aggregate."""
        query = select(FactorDefinition).order_by(FactorDefinition.category, FactorDefinition.code)
        if only_active:
            query = query.where(FactorDefinition.is_active.is_(True))
        return [definition_payload(definition) for definition in db.scalars(query).all()]

    def get_definition(self, db, code: str) -> FactorDefinition:
        definition = db.scalar(select(FactorDefinition).where(FactorDefinition.code == code))
        if not definition:
            raise FactorError(f"unknown factor: {code}")
        return definition

    def screen(
        self,
        db,
        specs: list[tuple[str, float]],
        *,
        trade_date: date | None = None,
        limit: int = 200,
    ) -> dict:
        """Intersect "top N% by factor" conditions into one candidate list.

        ``specs`` is ``[(factor_code, top_percent), …]``. Each factor is cut on its own latest
        available cross-section (or ``trade_date`` when given), ranked by the factor's direction,
        then the resulting code sets are intersected. Values and the trade date of every condition
        ride along so the caller can show the numbers behind the cut.
        """
        if not specs:
            raise FactorError("no factor conditions given")

        conditions: list[dict] = []
        codes: set[str] | None = None
        for code, top_percent in specs:
            definition = self.get_definition(db, code)
            day = trade_date or db.scalar(
                select(func.max(FactorValue.trade_date)).where(FactorValue.factor_id == definition.id)
            )
            if day is None:
                raise FactorError(f"{code} has no computed values")
            descending = definition.direction != "negative"
            value_col = FactorValue.value.desc() if descending else FactorValue.value.asc()
            rows = db.execute(
                select(FactorValue.ts_code, FactorValue.value)
                .where(FactorValue.factor_id == definition.id, FactorValue.trade_date == day)
                .order_by(value_col)
            ).all()
            if not rows:
                raise FactorError(f"{code} has no values on {day}")
            take = max(1, math.ceil(len(rows) * max(0.0, min(100.0, top_percent)) / 100))
            picked = rows[:take]
            selected = {ts_code for ts_code, _ in picked}
            codes = selected if codes is None else (codes & selected)
            conditions.append(
                {
                    "code": definition.code,
                    "name": definition.name,
                    "direction": definition.direction,
                    "unit": definition.unit,
                    "trade_date": day.isoformat(),
                    "coverage": len(rows),
                    "top_percent": top_percent,
                    "values": {ts_code: _float(value) for ts_code, value in picked},
                }
            )

        codes = codes or set()
        rows: list[dict] = []
        if codes:
            ordered = sorted(codes)[:limit]
            info = _stock_info(db, ordered)
            for ts_code in ordered:
                rows.append(
                    {
                        "ts_code": ts_code,
                        "name": info.get(ts_code, {}).get("name"),
                        "industry": info.get(ts_code, {}).get("industry"),
                        "values": {
                            condition["code"]: condition["values"].get(ts_code)
                            for condition in conditions
                        },
                    }
                )
        return {
            "trade_date": conditions[0]["trade_date"] if conditions else None,
            "factors": [
                {k: v for k, v in condition.items() if k != "values"} for condition in conditions
            ],
            "total": len(codes),
            "rows": rows,
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
        self.refresh_coverage(db, definition)
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

    def refresh_coverage(self, db, definition: FactorDefinition) -> dict:
        """Store what this factor now holds. One aggregate, run when values change."""
        stats = db.execute(
            select(
                func.count().label("rows"),
                func.count(func.distinct(FactorValue.ts_code)).label("stocks"),
                func.min(FactorValue.trade_date).label("first_date"),
                func.max(FactorValue.trade_date).label("last_date"),
            ).where(FactorValue.factor_id == definition.id)
        ).one()
        definition.value_count = int(stats.rows or 0)
        definition.stock_count = int(stats.stocks or 0)
        definition.first_date = stats.first_date
        definition.last_date = stats.last_date
        definition.computed_at = datetime.utcnow()
        db.commit()
        return {
            "value_count": definition.value_count,
            "stock_count": definition.stock_count,
            "first_date": definition.first_date,
            "last_date": definition.last_date,
        }

    def computable_codes(self, db) -> Iterable[str]:
        return db.scalars(
            select(FactorDefinition.code).where(FactorDefinition.formula.isnot(None))
        ).all()


def _stock_info(db, codes: list[str]) -> dict[str, dict]:
    """Name/industry for the screened codes, read from the read-only market-data table."""
    if not codes:
        return {}
    from sqlalchemy import text

    from app.core.tushare_schema import tushare_table

    sql = text(
        f"SELECT ts_code, name, industry FROM {tushare_table('stock_basic')} "
        f"WHERE ts_code IN ({', '.join(f':c{i}' for i in range(len(codes)))})"
    )
    result = db.execute(sql, {f"c{i}": code for i, code in enumerate(codes)}).all()
    return {row[0]: {"name": row[1], "industry": row[2]} for row in result}


def definition_payload(definition: FactorDefinition) -> dict:
    return {
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
        "value_count": int(definition.value_count or 0),
        "stock_count": int(definition.stock_count or 0),
        "first_date": definition.first_date,
        "last_date": definition.last_date,
        "computed_at": definition.computed_at,
    }


def _float(value) -> float | None:
    return None if value is None else float(value)
