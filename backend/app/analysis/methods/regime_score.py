"""Regime-aware score table: momentum when the index is above its MA, reversal when below.

The arithmetic is the one in `scripts/regime_score.py` (z-score the factors across the section, sign
them by regime, sum). The data path is different on purpose: the script asks `load_dataset` for factors
*joined with forward returns*, which for a 28-month window pulls millions of rows and OOM-killed the
API pod. Scoring needs no labels — only the factor values on the day — so this reads factor values
month by month and never materialises the whole window.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.analysis.artifact import ScoreTable
from app.analysis.registry import MethodSpec, register

DEFAULT_FACTORS = ("mom_20d", "MACD", "ma_dev_20")
CHUNK_DAYS = 21


class RegimeScoreParams(BaseModel):
    start: date
    end: date
    ma_window: int = Field(60, ge=5, le=250, description="指数均线窗口（交易日）")
    horizon: int = Field(20, ge=1, le=60, description="标签的前瞻期，只记录在 provenance 里")
    benchmark: str = Field("000300.SH", description="用于判定 regime 的指数")
    factors: list[str] = Field(default_factory=lambda: list(DEFAULT_FACTORS))
    exclude_st: bool = Field(True, description="剔除 ST")


def _factor_panel(db: Session, code: str, start: date, end: date) -> pd.DataFrame:
    """One factor widened to `date x code`. Read per factor so only one panel is in memory."""
    frame = pd.read_sql(
        text(
            "SELECT v.trade_date, v.ts_code, v.value FROM factor_values v "
            "JOIN factor_definitions d ON d.id = v.factor_id "
            "WHERE d.code = :code AND v.trade_date BETWEEN :start AND :end"
        ),
        db.connection(),
        params={"code": code, "start": start, "end": end},
    )
    if frame.empty:
        return pd.DataFrame()
    return frame.pivot_table(index="trade_date", columns="ts_code", values="value", aggfunc="last")


def _st_codes(db: Session) -> set[str]:
    from app.core.tushare_schema import tushare_table

    return {
        row[0]
        for row in db.execute(
            text(f"SELECT ts_code FROM {tushare_table('stock_basic')} WHERE name LIKE '%ST%'")
        ).all()
    }


def run(db: Session, params: RegimeScoreParams, dataset: dict | None = None) -> ScoreTable:
    from scripts.regime_score import market_regime

    panels = {code: _factor_panel(db, code, params.start, params.end) for code in params.factors}
    panels = {code: panel for code, panel in panels.items() if not panel.empty}
    if not panels:
        return ScoreTable(
            frame=pd.DataFrame(columns=["trade_date", "ts_code", "score"]),
            params=params.model_dump(mode="json"),
            dataset=dataset or {},
        )

    days = sorted(set().union(*[set(panel.index) for panel in panels.values()]))
    regime = market_regime(db, params.benchmark, params.start, params.end, params.ma_window)
    excluded = _st_codes(db) if params.exclude_st else set()

    rows: list[pd.DataFrame] = []
    for offset in range(0, len(days), CHUNK_DAYS):
        chunk = days[offset : offset + CHUNK_DAYS]
        frame = pd.DataFrame(index=chunk)
        columns = {}
        for code, panel in panels.items():
            sliced = panel.reindex(chunk)
            if excluded:
                sliced = sliced.drop(columns=[c for c in sliced.columns if c in excluded], errors="ignore")
            columns[code] = sliced
        if any(sliced.empty for sliced in columns.values()):
            continue
        # z-score each factor across the section, then sign by regime, then sum — the script's order.
        for code in columns:
            sliced = columns[code]
            mean = sliced.mean(axis=1)
            std = sliced.std(axis=1).replace(0, np.nan)
            columns[code] = sliced.sub(mean, axis=0).div(std, axis=0)
        composite = sum(columns.values())
        signs = pd.Series({day: 1.0 if regime.get(day, True) else -1.0 for day in chunk})
        composite = composite.mul(signs, axis=0)
        long = composite.stack().rename("score").reset_index()
        long.columns = ["trade_date", "ts_code", "score"]
        rows.append(long.dropna(subset=["score"]))
        del frame, composite, long

    if not rows:
        return ScoreTable(
            frame=pd.DataFrame(columns=["trade_date", "ts_code", "score"]),
            params=params.model_dump(mode="json"),
            dataset=dataset or {},
        )

    return ScoreTable(
        frame=pd.concat(rows, ignore_index=True),
        params=params.model_dump(mode="json"),
        label={"kind": "benchmark", "horizon": params.horizon, "benchmark": params.benchmark},
        dataset=dataset or {},
    )


METHOD = register(
    MethodSpec(
        name="regime_score",
        display_name="regime 打分（均线切换动量/反转）",
        description="指数在均线上方时给动量因子正号，下方时反号，合成截面分数；分数只排序，不决定买卖。",
        params_model=RegimeScoreParams,
        output_kind="score_table",
        needs_factors=DEFAULT_FACTORS,
        run=run,
    )
)
