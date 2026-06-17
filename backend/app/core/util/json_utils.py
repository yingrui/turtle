"""JSON-serialization helpers for API responses."""

from __future__ import annotations

import json

import pandas as pd


def dataframe_to_records(df: pd.DataFrame) -> list[dict]:
    """Convert a DataFrame to JSON-safe dict records (NaN/NaT → null)."""
    if df.empty:
        return []
    return json.loads(df.to_json(orient="records", date_format="iso"))
