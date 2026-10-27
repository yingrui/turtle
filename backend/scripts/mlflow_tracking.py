"""Log a scorecard run (and its model) to MLflow.

MLflow is the record of experiments: which window trained which model, on which data version, with
what metrics. openKMS keeps the *data* identity (dataset + version + sha256) and this module passes
it through as run tags, so a run in MLflow can be traced to an exact file.

Tracking URI comes from `MLFLOW_TRACKING_URI` (default the local server). If MLflow is unreachable
the training still succeeds — it prints a warning and returns `None`, because losing the audit trail
should not lose the model.

    from scripts.mlflow_tracking import log_scorecard_run
    info = log_scorecard_run(model=model, params=params, metrics=metrics,
                             artifacts={"model.json": path}, target_month="2026-02")
"""

from __future__ import annotations

import json
import os
from pathlib import Path

EXPERIMENT = "stock-scorecard"
MODEL_NAME = "scorecard-5d-relative"


def tracking_uri() -> str:
    return os.environ.get("MLFLOW_TRACKING_URI", "http://127.0.0.1:5000")


def log_scorecard_run(
    *,
    model: dict,
    params: dict,
    metrics: dict,
    artifacts: dict[str, Path],
    target_month: str,
    tags: dict[str, str] | None = None,
) -> dict | None:
    """Record one run and register its model version. Returns `{run_id, model_version, experiment}`."""
    try:
        import mlflow
        from mlflow.tracking import MlflowClient
    except ImportError:  # pragma: no cover - the dependency is declared; this is a safety net
        print("warning: mlflow is not installed; the run is not recorded")
        return None

    mlflow.set_tracking_uri(tracking_uri())
    try:
        mlflow.set_experiment(EXPERIMENT)
        client = MlflowClient()
        experiment_id = client.get_experiment_by_name(EXPERIMENT).experiment_id

        with mlflow.start_run(run_name=f"{MODEL_NAME}-{target_month}") as run:
            mlflow.log_params({**_flatten(params), "target_month": target_month})
            mlflow.log_metrics({k: v for k, v in _flatten(metrics).items() if isinstance(v, (int, float))})
            for name, path in artifacts.items():
                mlflow.log_artifact(str(path))
            dataset = model.get("dataset") or {}
            run_tags = {
                "target_month": target_month,
                "label_kind": str(params.get("label")),
                "horizon": str(params.get("horizon")),
                "factors": ",".join(f["code"] for f in model.get("factors", [])),
                "dataset": str(dataset.get("name") or ""),
                "dataset_version": str(dataset.get("version") or ""),
                "dataset_sha256": str(dataset.get("sha256") or ""),
                **(tags or {}),
            }
            mlflow.set_tags(run_tags)
            run_id = run.info.run_id

        # A model version per monthly run: the registry is how "which month used which model" is
        # answered without reading a directory listing.
        version = mlflow.register_model(f"runs:/{run_id}/model.json", MODEL_NAME)
        client.set_model_version_tag(MODEL_NAME, version.version, "target_month", target_month)
        if dataset.get("version"):
            client.set_model_version_tag(
                MODEL_NAME, version.version, "dataset_version", str(dataset["version"])
            )
        client.update_model_version(
            MODEL_NAME, version.version, description=f"scorecard for {target_month}"
        )
        return {
            "run_id": run_id,
            "model_version": int(version.version),
            "experiment": EXPERIMENT,
            "experiment_id": experiment_id,
            "tracking_uri": tracking_uri(),
        }
    except Exception as exc:  # MLflow down / auth / schema drift: keep the model, say so
        print(f"warning: MLflow logging failed ({type(exc).__name__}: {exc}); the run is not recorded")
        return None


def _flatten(values: dict, prefix: str = "") -> dict:
    """MLflow params/metrics are scalars; nested dicts become dotted keys, lists become comma text."""
    flat: dict = {}
    for key, value in (values or {}).items():
        name = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(_flatten(value, prefix=f"{name}."))
        elif isinstance(value, (list, tuple)):
            flat[name] = ",".join(str(v) for v in value)
        elif isinstance(value, bool):
            flat[name] = str(value)
        elif isinstance(value, (int, float, str)) or value is None:
            flat[name] = value if value is not None else ""
        else:
            flat[name] = json.dumps(value, default=str)[:250]
    return flat
