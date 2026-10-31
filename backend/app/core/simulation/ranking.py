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


class IcWeightsRankingProvider:
    """Ranks by an IC-weight table written offline (`scripts/ic_weighted.py --export-weights`).

    The weights are a fact about the past: for each date, the mean cross-sectional IC of every factor
    over the preceding window. Scoring is a dot product with today's ranks, so nothing is fitted here —
    the simulation reads a table, exactly like it reads a model.
    """

    def __init__(self, path: str, *, exclude_st: bool = True) -> None:
        import json
        from pathlib import Path

        payload = json.loads(Path(path).read_text())
        self.factors: list[str] = payload["factors"]
        self.lookback: int = payload["lookback"]
        self.weights: dict[str, dict[str, float | None]] = payload["weights"]
        self.exclude_st = exclude_st
        self._dates = sorted(self.weights)

    def _weights_for(self, day: date) -> dict[str, float | None] | None:
        import bisect

        index = bisect.bisect_right(self._dates, day.isoformat()) - 1
        return self.weights[self._dates[index]] if index >= 0 else None

    def rankings(self, db, day: date) -> list[Ranked]:
        weights = self._weights_for(day)
        if not weights:
            return []
        ranks = rank_cross_section(db, day, self.factors)
        if ranks.empty:
            return []
        if self.exclude_st:
            from app.core.simulation.model_runner import _st_codes

            ranks = ranks[~ranks["ts_code"].isin(_st_codes(db))]
        if ranks.empty:
            return []
        score = []
        for _, row in ranks.iterrows():
            value = 0.0
            for factor, weight in weights.items():
                if weight is None:
                    continue
                value += weight * (float(row[factor]) - 0.5)
            score.append(value)
        ordered = sorted(zip(ranks["ts_code"].to_numpy(), score), key=lambda pair: pair[1], reverse=True)
        return [
            Ranked(ts_code=str(code), score=float(value), rank=index + 1)
            for index, (code, value) in enumerate(ordered)
        ]


class ScoreTableRankingProvider:
    """Ranks by a table of precomputed scores: `{date: {ts_code: score}}`.

    Used for rankings that come from an offline analysis rather than a model (experiment 2's IC
    weights, experiment 3's regime scores). The table is a fact about the past; scoring is a lookup.
    """

    def __init__(self, path: str) -> None:
        import json
        from pathlib import Path

        payload = json.loads(Path(path).read_text())
        self.dates: dict[str, dict[str, float]] = payload["dates"]
        self._ordered = sorted(self.dates)

    def rankings(self, db, day: date) -> list[Ranked]:
        import bisect

        index = bisect.bisect_right(self._ordered, day.isoformat()) - 1
        if index < 0:
            return []
        scores = self.dates[self._ordered[index]]
        ordered = sorted(scores.items(), key=lambda pair: pair[1], reverse=True)
        return [
            Ranked(ts_code=str(code), score=float(value), rank=position + 1)
            for position, (code, value) in enumerate(ordered)
        ]


class RankingSourceProvider:
    """Rank by a registered `ranking_sources` row — the online path.

    The job payload names a source id; the artifact it points at was validated when it was published,
    and the run records its sha256. No path is ever typed by a user.
    """

    def __init__(self, source_id: str) -> None:
        self.source_id = source_id
        self._cache: dict | None = None

    def rankings(self, db, day: date) -> list[Ranked]:
        from app.services.analysis_service import RankingSourceService

        service = RankingSourceService()
        source = service.get(db, self.source_id)
        if self._cache is None:
            from app.analysis.artifact import read_scores

            self._cache = read_scores(source.artifact_key)
        from app.analysis.artifact import scores_on_or_before

        frame = scores_on_or_before(self._cache, day)
        if frame.empty:
            return []
        ordered = frame.sort_values("score", ascending=False)
        return [
            Ranked(ts_code=str(row.ts_code), score=float(row.score), rank=position + 1)
            for position, row in enumerate(ordered.itertuples())
        ]

    def describe(self) -> dict:
        return {"source": "ranking_source", "source_id": self.source_id}


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
    "IcWeightsRankingProvider",
    "ModelUnavailable",
    "ModelRankingProvider",
    "Ranked",
    "RankingProvider",
    "ScoreTableRankingProvider",
    "RankingSourceProvider",
    "StaticRankingProvider",
]
