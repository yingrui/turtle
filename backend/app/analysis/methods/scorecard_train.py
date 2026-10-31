"""Train a scorecard for one period and store it as a model artifact.

This is `scripts/scorecard.py` behind the analysis runner. The model is a **parameter file** (intercept,
per-factor WOE bins and coefficients), never a pickle: loading a pickle is arbitrary code execution and
makes the artifact unauditable. The runner hashes it and registers it under a fingerprint built from the
inputs, so a simulation asking for the same period and the same data reuses it instead of retraining.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.analysis.registry import MethodSpec, register

DEFAULT_FACTORS = ("liq_turn_std_6M", "mom_20d", "MACD", "ma_dev_20", "RSI", "vol_60d", "Ln_MC", "ATR")


class ScorecardTrainParams(BaseModel):
    period: str = Field(..., description="训练目标周期，如 2025-07")
    start: date = Field(..., description="训练窗口起点")
    end: date = Field(..., description="训练窗口终点（含当月第一天之前的最后一个交易日）")
    label: str = Field("benchmark", description="benchmark | relative | absolute")
    horizon: int = Field(20, ge=1, le=60)
    benchmark: str = Field("000300.SH")
    bins: int = Field(10, ge=3, le=30)
    min_iv: float = Field(0.02, ge=0.0, le=1.0)
    max_corr: float = Field(0.7, ge=0.0, le=1.0)
    factors: list[str] = Field(default_factory=lambda: list(DEFAULT_FACTORS))
    exclude_st: bool = True


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
        display_name="训练评分卡（单期）",
        description="用给定窗口训练一套 WOE + 逻辑回归评分卡；同输入同周期会复用已有模型，不重复训练。",
        params_model=ScorecardTrainParams,
        output_kind="model",
        needs_factors=DEFAULT_FACTORS,
        run=run,
    )
)
