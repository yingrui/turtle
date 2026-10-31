"""Strategies: the trade rules a run may choose, with their parameter schemas."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.core.simulation import strategies
from app.models.user import User

router = APIRouter(prefix="/api/strategies", tags=["strategies"], dependencies=[Depends(get_current_user)])


@router.get("")
def list_strategies(_: User = Depends(get_current_user)):
    return {"strategies": strategies.describe()}


@router.get("/{name}")
def get_strategy(name: str, _: User = Depends(get_current_user)):
    try:
        spec = strategies.get(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown strategy: {name}") from None
    return {
        "name": spec.name,
        "display_name": spec.display_name,
        "description": spec.description,
        "params_schema": spec.params_model.model_json_schema(),
    }
