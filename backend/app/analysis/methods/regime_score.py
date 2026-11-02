"""Regime-aware score table: momentum when the index is above its MA, reversal when below.

The arithmetic is the one in `scripts/regime_score.py` (z-score the factors across the section, sign
them by regime, sum). The data path is different on purpose: the script asks `load_dataset` for factors
*joined with forward returns*, which for a 28-month window pulls millions of rows and OOM-killed the
API pod. Scoring needs no labels — only the factor values on the day — so this reads factor values
month by month and never materialises the whole window.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.analysis.artifact import ScoreTable
from app.analysis.registry import MethodSpec, register

DEFAULT_FACTORS = ("mom_20d", "MACD", "ma_dev_20")


class RegimeScoreParams(BaseModel):
    start: date = Field(..., title="计算起点")
    end: date = Field(..., title="计算终点")
    ma_window: int = Field(60, ge=5, le=250, title="均线周期（交易日）", description="用多少日均线判别趋势/震荡，常用 60")
    horizon: int = Field(20, ge=1, le=60, description="标签的前瞻持有期，只记录在数据说明里，不影响当日打分")
    benchmark: str = Field("000300.SH", title="基准指数", description="用它的均线判别市场状态，通常沪深300")
    # 因子不开放选择：这个算法就是"对动量类因子按大盘方向改符号"，换成价值因子会得到一个没有意义的负暴露。
    exclude_st: bool = Field(True, title="剔除 ST 股", description="ST 是交易所对异常公司的标记")


def _months(start: date, end: date):
    cursor = start
    while cursor <= end:
        month_end = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        yield cursor, min(month_end, end)
        cursor = min(month_end, end) + timedelta(days=1)


def run(db: Session, params: RegimeScoreParams, dataset: dict | None = None) -> ScoreTable:
    """One month at a time, through the script's own `load_dataset`.

    The whole window in one call is what OOM-killed the API pod; re-implementing the scoring by hand is
    what made the top-50 disagree with the offline export (48% overlap: that code is Σ(rank−0.5) over
    the *labelled, non-ST* universe, not a z-score over every code with a factor value). So: same
    function, smaller slices. The slice is widened past the month end so the label for the month's last
    days is available, then trimmed back to the month.
    """
    from scripts.regime_score import market_regime, score
    from scripts.scorecard import load_dataset

    lookahead = timedelta(days=params.horizon * 2)
    regime = market_regime(db, params.benchmark, params.start, params.end + lookahead, params.ma_window)

    frames: list[pd.DataFrame] = []
    for month_start, month_end in _months(params.start, params.end):
        chunk = load_dataset(
            db,
            start=month_start,
            end=month_end + lookahead,
            horizon=params.horizon,
            label="benchmark",
            benchmark=params.benchmark,
            exclude_st=params.exclude_st,
        )
        frame = chunk.frame
        if frame.empty:
            continue
        factors = [code for code in DEFAULT_FACTORS if code in frame.columns]
        if not factors:
            break
        days = pd.to_datetime(frame["trade_date"]).dt.strftime("%Y-%m-%d")
        inside = (days >= month_start.isoformat()) & (days <= month_end.isoformat())
        frame = frame[inside]
        if frame.empty:
            continue
        frame = frame.copy()
        frame["trade_date"] = days[inside]
        values = score(frame, factors, regime, flip=True)
        frames.append(
            pd.DataFrame(
                {
                    "trade_date": frame["trade_date"].to_numpy(),
                    "ts_code": frame["ts_code"].to_numpy(),
                    "score": values,
                }
            ).dropna(subset=["score"])
        )
        del chunk, frame

    if not frames:
        return ScoreTable(
            frame=pd.DataFrame(columns=["trade_date", "ts_code", "score"]),
            params=params.model_dump(mode="json"),
            dataset=dataset or {},
        )

    return ScoreTable(
        frame=pd.concat(frames, ignore_index=True),
        params=params.model_dump(mode="json"),
        label={"kind": "benchmark", "horizon": params.horizon, "benchmark": params.benchmark},
        dataset=dataset or {},
    )


METHOD = register(
    MethodSpec(
        name="regime_score",
        display_name="跟大盘方向切换动量/反转",
        description=(
            "看大盘方向决定买强还是买弱：把沪深300 今天的收盘点位，和它自己最近 60 个交易日收盘价的平均值比高低。"
            "今天收盘高于这个平均值，认为行情在涨，买近期涨得多的；低于平均值，认为行情在跌，反过来买近期跌得多的。"
            "每天把 20 日动量、MACD、20 日乖离率这三个指标在全市场排一次名，名次越靠前分数越高，三个分数相加就是总分。"
            "因子固定为这三个，不可更换 —— 换成别的指标（比如估值、财务）这个逻辑就不成立了。"
        ),
        params_model=RegimeScoreParams,
        output_kind="score_table",
        needs_factors=DEFAULT_FACTORS,
        run=run,
    )
)
