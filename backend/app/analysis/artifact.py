"""Score-table artifacts: parquet + card, content addressed.

A table is the interchange format for "an offline analysis decided these scores". JSON at 3.4M rows was
66 MB held in memory per run; parquet is columnar, slices by date, and carries its own schema.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pandas as pd

ARTIFACT_ROOT = Path(os.environ.get("STOCK_RANKINGS_DIR", "reports/rankings"))


@dataclass
class ScoreTable:
    """Scores by (trade_date, ts_code), plus the metadata a card needs."""

    frame: pd.DataFrame                  # columns: trade_date, ts_code, score
    params: dict = field(default_factory=dict)
    label: dict = field(default_factory=dict)
    dataset: dict = field(default_factory=dict)

    def summary(self) -> dict:
        if self.frame.empty:
            return {"row_count": 0, "date_from": None, "date_to": None, "universe_size": 0}
        days = pd.to_datetime(self.frame["trade_date"])
        return {
            "row_count": int(len(self.frame)),
            "date_from": days.min().date().isoformat(),
            "date_to": days.max().date().isoformat(),
            "universe_size": int(self.frame["ts_code"].nunique()),
        }


def write_score_table(source_id: str, table: ScoreTable) -> tuple[str, str]:
    """Write the artifact and return `(key, sha256)`. Re-writing an identical table reuses the sha."""
    frame = table.frame.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.date
    frame["score"] = frame["score"].astype("float32")
    payload = frame[["trade_date", "ts_code", "score"]].sort_values(["trade_date", "ts_code"])
    digest = hashlib.sha256(
        pd.util.hash_pandas_object(payload, index=False).to_numpy().tobytes()
    ).hexdigest()
    directory = ARTIFACT_ROOT / source_id / digest
    directory.mkdir(parents=True, exist_ok=True)
    payload.to_parquet(directory / "scores.parquet", index=False, compression="zstd")
    (directory / "card.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "kind": "score_table",
                "source_id": source_id,
                "columns": ["trade_date", "ts_code", "score"],
                "params": table.params,
                "label": table.label,
                "dataset": table.dataset,
                **(table.summary()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return str(directory), digest


def read_scores(artifact_key: str) -> pd.DataFrame:
    path = Path(artifact_key) / "scores.parquet"
    if not path.exists():
        raise FileNotFoundError(f"ranking artifact missing: {path}")
    return pd.read_parquet(path)


def scores_on_or_before(frame: pd.DataFrame, day: date) -> pd.DataFrame:
    """Carry-forward: the latest scored session at or before `day`.

    Same semantics the JSON provider used — a score computed on Friday is still the newest information
    on a Monday holiday.
    """
    days = pd.to_datetime(frame["trade_date"]).dt.date
    usable = days <= day
    if not usable.any():
        return frame.iloc[0:0]
    latest = days[usable].max()
    return frame[days == latest]
