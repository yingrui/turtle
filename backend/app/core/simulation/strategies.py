"""Trade rules as a registry, not an enum.

`buy_rule: "policy" | "mechanical"` would not survive a third strategy. Each entry declares the
parameters it needs and how it decides; sizing, fees and tradability stay in the runner, so two
strategies can never account for costs differently.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, Field


class PoolEntryParams(BaseModel):
    """Buy on entering the pool; exits come from the portfolio's policy."""

    cash_buffer: float = Field(0.05, ge=0, le=1)
    max_holdings: int = Field(50, ge=1, le=500)


class PolicyBothSidesParams(BaseModel):
    """The policy decides both sides — meaningful only for a stable watchlist."""

    cash_buffer: float = Field(0.05, ge=0, le=1)


class MechanicalParams(BaseModel):
    top_n: int = Field(50, ge=1, le=500)
    hold_days: int = Field(20, ge=1, le=250)
    cash_buffer: float = Field(0.05, ge=0, le=1)


@dataclass(frozen=True)
class StrategySpec:
    name: str
    display_name: str
    description: str
    params_model: type[BaseModel]
    enter_on_pool: bool = False
    extra: dict = field(default_factory=dict)


_REGISTRY: dict[str, StrategySpec] = {}


def register(spec: StrategySpec) -> StrategySpec:
    _REGISTRY[spec.name] = spec
    return spec


def get(name: str) -> StrategySpec:
    if name not in _REGISTRY:
        raise KeyError(f"unknown strategy: {name}")
    return _REGISTRY[name]


def describe() -> list[dict]:
    return [
        {
            "name": spec.name,
            "display_name": spec.display_name,
            "description": spec.description,
            "params_schema": spec.params_model.model_json_schema(),
        }
        for spec in sorted(_REGISTRY.values(), key=lambda item: item.name)
    ]


register(StrategySpec(
    name="pool_entry",
    display_name="进池即买，policy 负责卖",
    description="池决定入场，组合 policy 决定出场；适合每天更换的池子。",
    params_model=PoolEntryParams,
    enter_on_pool=True,
))
register(StrategySpec(
    name="policy",
    display_name="policy 决定买卖",
    description="池与 policy 都参与决策；适合固定的自选列表。",
    params_model=PolicyBothSidesParams,
))
register(StrategySpec(
    name="mechanical",
    display_name="机械持有（排序诊断）",
    description="买 Top-N、持有固定天数；衡量排序本身，不代表策略收益。",
    params_model=MechanicalParams,
))
