"""What a simulation needs from a model: an ordered list of stocks per day.

The runner trades a ranking; it has no business knowing what produced it. Splitting the two means the
label, the features, the model family and the dataset version can all change without touching the
simulation, and a different ranking source (a rule, a manual list, another model) plugs in by
implementing this one method.

A provider returns **every** scored stock with its rank, because the sell rule asks "how far did it
fall?", not just "is it in the top N?".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from app.core.factor.score import ModelUnavailable, load_model_for, rank_cross_section, score_frame


@dataclass(frozen=True)
class Ranked:
    """One stock's place in the day's cross-section."""

    ts_code: str
    score: float
    rank: int


class RankingProvider(Protocol):
    """A day's ranking, best first."""

    def rankings(self, db, day: date) -> list[Ranked]:
        ...


class ModelRankingProvider:
    """Ranks by a trained scorecard: the monthly model for that date, on that day's factors.

    Everything model-specific lives here — which model directory, which factors, how a score is
    computed. The runner only sees `Ranked` rows.
    """

    def __init__(self, *, policy: str = "expanding", exclude_st: bool = True) -> None:
        self.policy = policy
        self.exclude_st = exclude_st

    def rankings(self, db, day: date) -> list[Ranked]:
        model = load_model_for(day, self.policy)
        codes = [factor["code"] for factor in model["factors"]]
        ranks = rank_cross_section(db, day, codes)
        if ranks.empty:
            return []
        if self.exclude_st:
            from app.core.simulation.model_runner import _st_codes  # local: avoids a cycle

            ranks = ranks[~ranks["ts_code"].isin(_st_codes(db))]
        if ranks.empty:
            return []
        scores = score_frame(model, ranks.drop(columns=["ts_code"]))
        ordered = sorted(
            zip(ranks["ts_code"].to_numpy(), scores), key=lambda pair: pair[1], reverse=True
        )
        return [
            Ranked(ts_code=str(code), score=float(score), rank=index + 1)
            for index, (code, score) in enumerate(ordered)
        ]


class StaticRankingProvider:
    """A fixed order per day — the "fixed pool" case, and the seam a test uses."""

    def __init__(self, order: list[str]) -> None:
        self.order = order

    def rankings(self, db, day: date) -> list[Ranked]:
        return [
            Ranked(ts_code=code, score=float(len(self.order) - index), rank=index + 1)
            for index, code in enumerate(self.order)
        ]


__all__ = [
    "ModelUnavailable",
    "ModelRankingProvider",
    "Ranked",
    "RankingProvider",
    "StaticRankingProvider",
]
