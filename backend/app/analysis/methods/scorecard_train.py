"""Train a scorecard for one period and store it as a model artifact.

This is `scripts/scorecard.py` behind the analysis runner. The model is a **parameter file** (intercept,
per-factor WOE bins and coefficients), never a pickle: loading a pickle is arbitrary code execution and
makes the artifact unauditable. The runner hashes it and registers it under a fingerprint built from the
inputs, so a simulation asking for the same period and the same data reuses it instead of retraining.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.analysis.registry import MethodSpec, register

DEFAULT_FACTORS = ("liq_turn_std_6M", "mom_20d", "MACD", "ma_dev_20", "RSI", "vol_60d", "Ln_MC", "ATR")


class ScorecardTrainParams(BaseModel):
    period: str = Field(..., title="目标月份", description="格式 2025-07，该模型用于 2025 年 7 月")
    start: date = Field(
        ...,
        title="训练数据起点",
        description="数据取自库内行情与因子表，非数据集文件；训练行数将记入模型",
    )
    end: date = Field(
        ..., title="训练数据终点", description="通常取目标月份之前最后一个交易日"
    )
    label: Literal["benchmark", "relative", "absolute"] = Field(
        "benchmark", title="预测目标", description="模型学的是跑赢基准、相对排名，还是绝对上涨"
    )
    horizon: int = Field(20, ge=1, le=60, title="持有期（交易日）", description="预测未来多少个交易日的表现")
    benchmark: str = Field("000300.SH", title="基准指数", description="判断跑赢与否用的参照")
    bins: int = Field(10, ge=3, le=30, title="分箱数", description="每个因子切成几档，常用 10")
    min_iv: float = Field(0.02, ge=0.0, le=1.0, title="最小 IV", description="信息量低于这个值的因子直接丢掉")
    max_corr: float = Field(0.7, ge=0.0, le=1.0, title="最大相关性", description="两个因子相关性超过它，只留一个")
    factors: list[str] = Field(default_factory=lambda: list(DEFAULT_FACTORS), title="候选因子", description="参与筛选的因子，最终用哪些由 IV 和相关性决定")
    exclude_st: bool = Field(True, title="剔除 ST 股", description="ST 是交易所对异常公司的标记，这类股票通常不参与建模")


def run(db: Session, params: ScorecardTrainParams, dataset: dict | None = None) -> dict:
    """Return the model payload; the runner writes and registers it."""
    from scripts.scorecard import build_model, load_dataset

    train = load_dataset(
        db,
        start=params.start,
        end=params.end,
        horizon=params.horizon,
        label=params.label,
        benchmark=params.benchmark,
        factors=list(params.factors),
        exclude_st=params.exclude_st,
    )
    model = build_model(
        train, horizon=params.horizon, label=params.label,
        min_iv=params.min_iv, max_corr=params.max_corr,
    )
    model["schema_version"] = 1
    model["scorer"] = "linear_woe"
    model["trained_for_period"] = params.period
    model["label"] = {"kind": params.label, "horizon": params.horizon, "benchmark": params.benchmark}
    model["inputs"] = {
        "factors": [{"code": factor["code"], "version": 1} for factor in model.get("factors", [])],
    }
    model["dataset"] = dataset or {}
    return model


METHOD = register(
    MethodSpec(
        name="scorecard_train",
        display_name="横截面评分卡（WOE + 逻辑回归，单期训练）",
        description=(
            "用给定窗口训练一个二分类模型：把每个因子按分箱做 WOE 编码，再拟合带 L2 正则的逻辑回归，"
            "输出每只股票次日到持有期末跑赢基准的概率，按概率排序。因子先按 IV 筛选、再去掉高相关，"
            "同一份数据与同一期不会重复训练。"
        ),
        params_model=ScorecardTrainParams,
        output_kind="model",
        needs_factors=DEFAULT_FACTORS,
        run=run,
    )
)
