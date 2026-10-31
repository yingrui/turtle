"""The method registry: what can be run, and what it needs.

A method is code plus a declared contract (params schema, output kind, inputs). The runner does the
storage, hashing and registration, so a method is testable without a database or a bucket, and the
audit trail lives in exactly one place.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from pydantic import BaseModel


@dataclass(frozen=True)
class MethodSpec:
    name: str
    display_name: str
    description: str
    params_model: type[BaseModel]
    output_kind: str                     # "score_table" | "model"
    needs_factors: tuple[str, ...] = ()  # validated against factor_definitions before running
    #: `analysis` computes scores from data. `control` builds a basket with no model behind it — it
    #: belongs where controls are declared, not on the analysis page.
    family: str = "analysis"
    run: Callable[..., object] | None = None


_REGISTRY: dict[str, MethodSpec] = {}


def register(spec: MethodSpec) -> MethodSpec:
    _REGISTRY[spec.name] = spec
    return spec


def get(name: str) -> MethodSpec:
    if name not in _REGISTRY:
        raise KeyError(f"unknown analysis method: {name}")
    return _REGISTRY[name]


def all_methods() -> list[MethodSpec]:
    return sorted(_REGISTRY.values(), key=lambda spec: spec.name)


def describe() -> list[dict]:
    """What the UI needs to render a form per method."""
    return [
        {
            "name": spec.name,
            "display_name": spec.display_name,
            "description": spec.description,
            "output_kind": spec.output_kind,
            "family": spec.family,
            "params_schema": spec.params_model.model_json_schema(),
        }
        for spec in all_methods()
    ]
