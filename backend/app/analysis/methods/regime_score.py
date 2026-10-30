"""Regime-aware score table: momentum when the index is above its MA, reversal when below.

This is `scripts/regime_score.py` turned into a method: the script's analysis (compute the factors,
sign them by regime, keep the cross-section) is unchanged; what is new is that the output is an
artifact a simulation can reference by id instead of a 66 MB JSON file passed by path.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.analysis.artifact import ScoreTable
from app.analysis.registry import MethodSpec, register

DEFAULT_FACTORS = ("mom_20d", "MACD", "ma_dev_20")


class RegimeScoreParams(BaseModel):
    start: date
    end: date
    ma_window: int = Field(60, ge=5, le=250, description="指数均线窗口（交易日）")
    horizon: int = Field(20, ge=1, le=60)
    benchmark: str = Field("000300.SH", description="用于判定 regime 的指数")
    factors: list[str] = Field(default_factory=lambda: list(DEFAULT_FACTORS))
    score_by_rank: bool = Field(True, description="按截面排名给分（否则用 z-score 合成）")


def _zscore(frame: pd.DataFrame) -> pd.DataFrame:
    return (frame - frame.mean(axis=1).to_frame().values) / frame.std(axis=1).replace(0, np.nan).to_frame().values


def run(db: Session, params: RegimeScoreParams, dataset: dict | None = None) -> ScoreTable:
    from app.core.simulation.model_runner import _trade_days
    from app.services.factor_service import FactorService

    days = _trade_days(db, params.start, params.end)
    if not days:
        return ScoreTable(frame=pd.DataFrame(columns=["trade_date", "ts_code", "score"]),
                          params=params.model_dump(mode="json"), dataset=dataset or {})

    service = FactorService()
    panels = {}
    for code in params.factors:
        frame = service.load_panel(db, [code], params.start, params.end)
        if not frame.empty:
            panels[code] = frame[frame.columns[0]]

    regime = _index_above_ma(db, params.benchmark, days, params.ma_window)

    rows = []
    for day in days:
        cross = pd.DataFrame({code: panel.loc[day] for code, panel in panels.items() if day in panel.index})
        if cross.empty:
            continue
        cross = cross.dropna(how="all")
        if cross.empty:
            continue
        sign = 1.0 if regime.get(day, True) else -1.0
        composite = (_zscore(cross) * sign).sum(axis=1, min_count=1)
        composite = composite.dropna()
        if composite.empty:
            continue
        if params.score_by_rank:
            ordered = composite.sort_values(ascending=False)
            scores = pd.Series(np.arange(len(ordered), 0, -1, dtype="float32"), index=ordered.index)
        else:
            scores = composite.astype("float32")
        for code, score in scores.items():
            rows.append({"trade_date": day, "ts_code": str(code), "score": float(score)})

    return ScoreTable(
        frame=pd.DataFrame(rows, columns=["trade_date", "ts_code", "score"]),
        params=params.model_dump(mode="json"),
        label={"kind": "relative", "horizon": params.horizon},
        dataset=dataset or {},
    )


def _index_above_ma(db: Session, benchmark: str, days: list[date], window: int) -> dict[date, bool]:
    """`index_daily` up to each day, close vs its own moving average."""
    from sqlalchemy import text

    from app.core.util.tables import tushare_table

    closes = [
        (row[0], float(row[1]))
        for row in db.execute(
            text(
                f"SELECT trade_date, close FROM {tushare_table('index_daily')} "
                "WHERE ts_code = :code ORDER BY trade_date"
            ),
            {"code": benchmark},
        ).all()
    ]
    series = pd.Series({d: price for d, price in closes}).sort_index()
    if series.empty:
        return {}
    average = series.rolling(window).mean()
    return {day: bool(series.get(day, np.nan) > average.get(day, np.nan)) for day in days}


METHOD = register(
    MethodSpec(
        name="regime_score",
        display_name="regime 打分（均线切换动量/反转）",
        description="指数在均线上方时给动量因子正号，下方时反号，合成截面分数。",
        params_model=RegimeScoreParams,
        output_kind="score_table",
        needs_factors=DEFAULT_FACTORS,
        run=run,
    )
)
