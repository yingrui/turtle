"""A fixed basket of stocks, optionally re-weighted: the control group as a method.

Experiment 1-3 needed "the same strategy on an arbitrary basket" to know how much of a result was
skill and how much was the basket. Doing that by hand produced JSON files nobody could trace back;
as a method it is a registered artifact like any other.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.analysis.artifact import ScoreTable
from app.analysis.registry import MethodSpec, register



class ConstantPoolParams(BaseModel):
    codes: list[str] = Field(default_factory=list, description="池内股票代码；留空则随机抽取")
    size: int = Field(50, ge=1, le=500, description="随机抽取的数量（codes 为空时生效）")
    seed: int = Field(0, description="随机种子，保证同一实验可复现")
    start: date
    end: date
    score_by_rank: bool = Field(True, description="按池内顺序给递减分数，否则全部同分")


def run(db: Session, params: ConstantPoolParams, dataset: dict | None = None) -> ScoreTable:
    import random

    from app.core.simulation.model_runner import _trade_days
    from app.core.util.tables import tushare_table

    days = _trade_days(db, params.start, params.end)
    codes = list(params.codes)
    if not codes:
        universe = sorted(
            row[0]
            for row in db.execute(
                text(f"SELECT ts_code FROM {tushare_table('stock_basic')} WHERE list_status = 'L'")
            ).all()
        )
        codes = random.Random(params.seed).sample(universe, min(params.size, len(universe)))
    rows = []
    for day in days:
        for position, code in enumerate(codes):
            score = float(len(codes) - position) if params.score_by_rank else 0.0
            rows.append({"trade_date": day, "ts_code": code, "score": score})
    return ScoreTable(
        frame=pd.DataFrame(rows, columns=["trade_date", "ts_code", "score"]),
        params=params.model_dump(mode="json"),
        dataset=dataset or {},
    )


METHOD = register(
    MethodSpec(
        name="constant_pool",
        display_name="固定池（对照组）",
        description="把选定的（或随机抽取的）一组股票作为池，全程不变；用于估计策略本身的基线收益。",
        params_model=ConstantPoolParams,
        output_kind="score_table",
        run=run,
    )
)
