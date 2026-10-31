"""Look up, or train-and-store, the model for a period.

`retrain` is the run's decision, not a global setting:

    monthly / weekly  train anything missing, reuse the rest
    none              never train; a missing period is an error, not a silent fallback
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models.model_artifact import ModelArtifact, fingerprint


class ModelUnavailable(Exception):
    """No model for this period and the run is not allowed to train one."""


class ModelArtifactService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, key: str) -> ModelArtifact | None:
        return self.db.get(ModelArtifact, key)

    def resolve(
        self,
        *,
        period: str,
        period_kind: str,
        method: str,
        params: dict,
        factors: list,
        label: dict,
        dataset: dict,
        retrain: str = "none",
        train=None,
        trained_by: str | None = None,
    ) -> tuple[ModelArtifact, str]:
        """Return `(artifact, "hit" | "trained")`."""
        key = fingerprint(
            method=method, period=period, period_kind=period_kind, params=params,
            factors=factors, label=label, dataset=dataset,
        )
        existing = self.get(key)
        if existing is not None and existing.status == "published":
            return existing, "hit"
        if retrain == "none" or train is None:
            raise ModelUnavailable(f"no model for {period} ({key[:12]}) and retrain={retrain}")
        artifact = train(key)
        artifact.trained_by = trained_by
        self.db.merge(artifact)
        self.db.commit()
        return artifact, "trained"


def period_of(day: date, kind: str) -> str:
    """`2025-07` for months, `2025-W31` for weeks — the labels a model cache is keyed by."""
    if kind == "week":
        year, week, _ = day.isocalendar()
        return f"{year}-W{week:02d}"
    return f"{day.year}-{day.month:02d}"
