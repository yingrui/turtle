"""Trained models as cached, content-addressed artifacts.

A model-driven run retrains per period — monthly or weekly, the run decides. Retraining is the
expensive part, so it is keyed by everything that determines the result: dataset version and manifest,
the factor set *and their versions*, hyperparameters, the label, and the period. Same fingerprint, same
model: skip training. Anything different — including a changed factor formula — makes a new one.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")


class ModelArtifact(Base):
    __tablename__ = "model_artifacts"

    #: sha256 over the fingerprint inputs; also the primary key so training is idempotent.
    fingerprint: Mapped[str] = mapped_column(String(64), primary_key=True)
    method: Mapped[str] = mapped_column(String(64))          # scorecard_train
    period: Mapped[str] = mapped_column(String(16))          # 2025-07 / 2025-W31
    period_kind: Mapped[str] = mapped_column(String(8))      # month | week
    params: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, server_default="{}")
    factors: Mapped[dict] = mapped_column(JSON_TYPE, default=list, server_default="[]")
    label: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, server_default="{}")
    dataset_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dataset_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dataset_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    artifact_key: Mapped[str] = mapped_column(String(512))
    artifact_sha256: Mapped[str] = mapped_column(String(64))
    metrics: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, server_default="{}")
    status: Mapped[str] = mapped_column(String(16), default="published")
    trained_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


def fingerprint(
    *,
    method: str,
    period: str,
    period_kind: str,
    params: dict,
    factors: list[dict] | list[str],
    label: dict,
    dataset: dict,
) -> str:
    """The identity of a training result.

    `factors` carries `(code, version)` pairs: bumping a factor's version must invalidate models,
    otherwise a formula change silently keeps a model trained on the old inputs.
    """
    payload = json.dumps(
        {
            "method": method,
            "period": period,
            "period_kind": period_kind,
            "params": params,
            "factors": sorted(
                (item if isinstance(item, str) else f"{item['code']}@v{item.get('version', 1)}")
                for item in factors
            ),
            "label": label,
            "dataset": {
                "name": dataset.get("name"),
                "version": dataset.get("version"),
                "manifest_sha256": dataset.get("manifest_sha256") or dataset.get("sha256"),
            },
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode()).hexdigest()
