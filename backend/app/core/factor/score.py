"""Scoring a cross-section with a trained scorecard, and finding the model for a date.

The model files are written by `scripts/train_monthly.py` (`reports/models/<policy>/<YYYY-MM>.json`).
Two callers use this module: the research scripts and the simulation runner, so a backtest scores
exactly the way the offline evaluation did — one implementation, not two.

A date resolves to the model trained **for that month**; when a month has no model, the most recent
earlier one is used. It never resolves forward in time: a model that has seen the future cannot score
the past.
"""

from __future__ import annotations

import json
import os
from datetime import date
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

#: Missing factor values are ranked neutral rather than dropped.
NEUTRAL_RANK = 0.5

#: `reports/models/` in the repository. In a deployment the directory is whatever
#: `STOCK_MODELS_DIR` points at (a mounted volume, or the image if the models are baked in).
MODELS_ROOT = Path(
    os.environ.get("STOCK_MODELS_DIR")
    or Path(__file__).resolve().parents[4] / "reports" / "models"
)


class ModelUnavailable(RuntimeError):
    """No model exists for that date and no earlier one either."""


def score_frame(model: dict, ranks: pd.DataFrame) -> np.ndarray:
    """Points: intercept plus each factor's WOE at the row's decile, times its coefficient."""
    score = np.full(len(ranks), model["intercept"])
    for factor in model["factors"]:
        if factor["code"] not in ranks.columns:
            continue
        series = ranks[factor["code"]].fillna(NEUTRAL_RANK)
        index = np.clip((series.to_numpy() * model["bins"]).astype(int), 0, model["bins"] - 1)
        score += factor["coef"] * np.asarray(factor["woe"])[index]
    return score


@lru_cache(maxsize=64)
def _read_model(path: str) -> dict:
    return json.loads(Path(path).read_text())


def model_index(policy: str = "expanding", root: Path | None = None) -> dict:
    index_path = (root or MODELS_ROOT) / policy / "index.json"
    if not index_path.exists():
        raise ModelUnavailable(f"no model index at {index_path}")
    return json.loads(index_path.read_text())


def model_path_for(day: date, policy: str = "expanding", root: Path | None = None) -> Path:
    """The model for that month, or the latest earlier month that has one.

    The file is resolved **next to the index** rather than through the recorded path: an index written
    on a laptop says `/Users/…/2026-09.json`, which means nothing inside a container.
    """
    base = (root or MODELS_ROOT) / policy
    index = model_index(policy, root)
    month = f"{day.year:04d}-{day.month:02d}"
    usable = sorted(
        m for m, entry in index.items() if not entry.get("skipped") and m <= month
    )
    for candidate_month in reversed(usable):
        candidate = base / f"{candidate_month}.json"
        if candidate.exists():
            return candidate
        recorded = index[candidate_month].get("model_path")
        if recorded and Path(recorded).exists():
            return Path(recorded)
    raise ModelUnavailable(f"no model trained for {month} or earlier (policy {policy})")


def load_model_for(day: date, policy: str = "expanding", root: Path | None = None) -> dict:
    return _read_model(str(model_path_for(day, policy, root)))


def rank_cross_section(db, day: date, codes: list[str]) -> pd.DataFrame:
    """The day's cross-section, ranked per factor within the day (0..1) — the training-time shape."""
    from sqlalchemy import text

    values = pd.read_sql(
        text(
            "SELECT v.ts_code, f.code, v.value "
            "FROM factor_values v JOIN factor_definitions f ON f.id = v.factor_id "
            "WHERE v.trade_date = :day AND f.code = ANY(:codes)"
        ),
        db.connection(),
        params={"day": day, "codes": codes},
    )
    if values.empty:
        return pd.DataFrame(columns=["ts_code", *codes])
    wide = values.pivot_table(index="ts_code", columns="code", values="value")
    wide = wide.reindex(columns=codes)
    return wide.rank(pct=True).fillna(NEUTRAL_RANK).reset_index()
