"""Run an analysis, publish its artifact, register the ranking source.

The method computes; this service owns everything that must be true of *every* artifact: it is written
once, hashed, described by a card, validated and registered under a stable id. That is why provenance
can be `{source_id, artifact_sha256}` instead of a path someone typed.
"""

from __future__ import annotations

import subprocess
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.analysis import methods  # noqa: F401  (registration side effect)
from app.analysis import registry
from app.analysis.artifact import ScoreTable, read_scores, scores_on_or_before, write_score_table
from app.models.ranking import AnalysisRun, RankingSource


def code_revision() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5
        ).stdout.strip() or None
    except Exception:
        return None


def default_source_id(method: str, params: dict) -> str:
    """Stable, human-readable id: the method plus its distinguishing parameters."""
    parts = [method]
    for key in ("ma_window", "horizon", "seed", "size"):
        if key in params and params[key] is not None:
            parts.append(f"{key}{params[key]}")
    return "-".join(parts).replace("_", "-")


def run_analysis(
    db: Session,
    *,
    method: str,
    params: dict,
    dataset: dict | None = None,
    source_id: str | None = None,
    display_name: str | None = None,
    created_by: str | None = None,
    run_id: str | None = None,
    progress=None,
) -> tuple[AnalysisRun, RankingSource]:
    spec = registry.get(method)
    parsed = spec.params_model(**params)
    # The API creates the row first so the caller gets an id immediately; the worker fills it in.
    run = db.get(AnalysisRun, run_id) if run_id else None
    if run is None:
        run = AnalysisRun(id=run_id or str(uuid.uuid4()), method=method, created_by=created_by)
        db.add(run)
    run.method = method
    run.params = parsed.model_dump(mode="json")
    run.dataset_name = (dataset or {}).get("name")
    run.dataset_version = (dataset or {}).get("version")
    run.status = "running"
    run.code_revision = code_revision()
    db.commit()

    try:
        table = spec.run(db, parsed, dataset or {})  # type: ignore[misc]
        if not isinstance(table, ScoreTable):
            raise TypeError(f"{method} returned {type(table).__name__}, expected ScoreTable")
        source_id = source_id or default_source_id(method, parsed.model_dump(mode="json"))
        key, digest = write_score_table(source_id, table)
        summary = table.summary()
        source = RankingSource(
            id=source_id,
            kind=spec.output_kind,
            display_name=display_name or spec.display_name,
            description=spec.description,
            method=method,
            params=parsed.model_dump(mode="json"),
            artifact_key=key,
            artifact_sha256=digest,
            row_count=summary["row_count"],
            date_from=summary["date_from"],
            date_to=summary["date_to"],
            universe_size=summary["universe_size"],
            dataset_name=(dataset or {}).get("name"),
            dataset_version=(dataset or {}).get("version"),
            dataset_sha256=(dataset or {}).get("manifest_sha256") or (dataset or {}).get("sha256"),
            label=table.label,
            status="published",
            validation=validate(table, spec),
            analysis_run_id=run.id,
            created_by=created_by,
        )
        db.merge(source)
        run.status = "completed"
        run.artifact_key = key
        run.artifact_sha256 = digest
        run.source_id = source_id
        run.finished_at = datetime.utcnow()
        db.commit()
        if progress:
            progress(f"{summary['row_count']:,} rows → {source_id}")
        return run, source
    except Exception as exc:  # noqa: BLE001 — the failure belongs on the run record
        run.status = "failed"
        run.error = f"{type(exc).__name__}: {exc}"
        run.finished_at = datetime.utcnow()
        db.commit()
        raise


def validate(table: ScoreTable, spec) -> dict:
    """Gate 1 (schema) and gate 3 (coverage) — cheap checks; smoke equivalence needs live factors."""
    frame = table.frame
    checks: list[dict] = []
    missing = {"trade_date", "ts_code", "score"} - set(frame.columns)
    checks.append({"gate": "schema", "ok": not missing, "detail": f"missing {sorted(missing)}" if missing else "ok"})
    checks.append(
        {
            "gate": "non_empty",
            "ok": bool(len(frame)),
            "detail": f"{len(frame):,} rows",
        }
    )
    dupes = int(frame.duplicated(["trade_date", "ts_code"]).sum()) if len(frame) else 0
    checks.append({"gate": "unique_keys", "ok": dupes == 0, "detail": f"{dupes} duplicates"})
    nan_scores = int(frame["score"].isna().sum()) if len(frame) else 0
    checks.append({"gate": "scores_present", "ok": nan_scores == 0, "detail": f"{nan_scores} NaN"})
    return {"checks": checks, "ok": all(check["ok"] for check in checks)}


class RankingSourceService:
    """Read paths a simulation uses: the list for the picker, and the daily ranking."""

    def list_sources(self, db: Session, include_deprecated: bool = False) -> list[dict]:
        query = db.query(RankingSource)
        if not include_deprecated:
            query = query.filter(RankingSource.status == "published")
        return [
            {
                "id": source.id,
                "kind": source.kind,
                "display_name": source.display_name,
                "description": source.description,
                "method": source.method,
                "params": source.params or {},
                "row_count": source.row_count,
                "date_from": source.date_from,
                "date_to": source.date_to,
                "universe_size": source.universe_size,
                "dataset": {
                    "name": source.dataset_name,
                    "version": source.dataset_version,
                    "manifest_sha256": source.dataset_sha256,
                },
                "label": source.label or {},
                "status": source.status,
                "validation": source.validation or {},
                "artifact_sha256": source.artifact_sha256,
                "created_at": source.created_at.isoformat() if source.created_at else None,
            }
            for source in query.order_by(RankingSource.created_at.desc()).all()
        ]

    def get(self, db: Session, source_id: str) -> RankingSource:
        source = db.get(RankingSource, source_id)
        if not source:
            raise KeyError(source_id)
        return source

    def preview(self, db: Session, source_id: str, day, limit: int = 20) -> list[dict]:
        source = self.get(db, source_id)
        frame = scores_on_or_before(read_scores(source.artifact_key), day)
        ordered = frame.sort_values("score", ascending=False).head(limit)
        return [
            {"ts_code": row.ts_code, "score": float(row.score), "rank": position + 1}
            for position, row in enumerate(ordered.itertuples())
        ]
