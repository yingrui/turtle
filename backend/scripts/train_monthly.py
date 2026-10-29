"""Train one scorecard per month, walk-forward, and register each in MLflow.

A month's model is trained on everything **before** that month and evaluated on the month itself —
which is exactly how it will be used, so the reported numbers are the simulation's own out-of-sample
record rather than a holdout invented after the fact.

    cd backend
    python -m scripts.train_monthly --from 2026-02 --to 2026-10
    python -m scripts.train_monthly --from 2026-02 --to 2026-10 --no-mlflow

Each model lands in `reports/models/<YYYY-MM>.json`; `reports/models/index.json` maps month → model,
MLflow run, model-registry version and the metrics measured on that month. `scripts/daily_selection`
reads that index, so a date always resolves to the model trained for its month.

Guards, because silently training on three weeks of data is how a "model" becomes a random number
generator:

- a month needs at least `--min-train-days` trading days of history and `--min-train-rows` rows;
- factors that exist in the training window are used; the rest are reported as missing;
- a month whose training window cannot satisfy the guards is skipped and said so.
"""

from __future__ import annotations

import argparse
import calendar
import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from app.database import SessionLocal
from scripts.mlflow_tracking import MODEL_NAME, dataset_reference, log_scorecard_run
from scripts.scorecard import Dataset, auc, build_model, load_dataset, score_frame

REPORTS = Path(__file__).resolve().parents[2] / "reports"
MODELS = REPORTS / "models"


def policy_dir(lookback_days: int | None, root: Path = MODELS, experiment: str | None = None) -> Path:
    """Each window policy is a directory; `--experiment` adds a suffix for a label/feature variant."""
    base = f"trailing{lookback_days}" if lookback_days else "expanding"
    return root / (f"{base}-{experiment}" if experiment else base)


def dataset_fingerprint(data: Dataset, *, horizon: int, label: str) -> str:
    """Identity of the panel a model saw: window, label definition, factors, and rows per date."""
    import hashlib

    counts = data.frame.groupby("trade_date").size()
    payload = json.dumps(
        {
            "start": data.dates[0].isoformat(),
            "end": data.dates[-1].isoformat(),
            "horizon": horizon,
            "label": label,
            "factors": sorted(data.factors),
            "rows": {str(k): int(v) for k, v in counts.items()},
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def month_start(month: str) -> date:
    return date.fromisoformat(f"{month}-01")


def month_end(month: str) -> date:
    year, mon = int(month[:4]), int(month[5:7])
    return date(year, mon, calendar.monthrange(year, mon)[1])


def next_months(start: str, end: str) -> list[str]:
    out, current = [], month_start(start)
    last = month_start(end)
    while current <= last:
        out.append(f"{current.year:04d}-{current.month:02d}")
        current = (current.replace(day=28) + timedelta(days=7)).replace(day=1)
    return out


def split_dates(dates: list[date], holdout: float) -> tuple[list[date], list[date]]:
    """Inner split of the training window: the tail validates the fit, nothing is evaluated twice."""
    cut = max(1, int(len(dates) * (1 - holdout)))
    if cut >= len(dates):
        raise SystemExit("inner holdout leaves nothing to validate on; widen the training window")
    return dates[:cut], dates[cut:]


def evaluate_on_month(model: dict, frame: pd.DataFrame) -> dict:
    """Out-of-sample metrics on the month the model will be used for."""
    scores = score_frame(model, frame)
    labels = frame["label"].to_numpy()
    scored = frame[["trade_date", "ts_code", "fwd_ret", "label"]].copy()
    scored["score"] = scores

    top_n = int(model.get("metrics", {}).get("top_n") or 10)
    picks = scored.sort_values(["trade_date", "score"], ascending=[True, False]).groupby("trade_date").head(top_n)
    per_date = picks.groupby("trade_date").agg(picked=("fwd_ret", "mean"))
    universe = scored.groupby("trade_date").agg(universe=("fwd_ret", "mean"))
    joined = per_date.join(universe)
    return {
        "target_month_auc": auc(scores, labels),
        "target_month_picked_ret": float(joined["picked"].mean()),
        "target_month_universe_ret": float(joined["universe"].mean()),
        "target_month_excess": float((joined["picked"] - joined["universe"]).mean()),
        "target_month_dates": int(joined.shape[0]),
    }


def train_month(db, month: str, args) -> dict:
    """Train on everything before `month`, evaluate on `month`. Returns the index entry."""
    train_end = month_start(month) - timedelta(days=1)
    # A growing window keeps every regime seen so far; a trailing one follows the current one. The
    # second is often what a monthly retrain wants, so it is a flag rather than a rewrite.
    start = args.start or date(2026, 1, 5)
    if args.lookback_days:
        start = max(start, train_end - timedelta(days=args.lookback_days))
    if train_end < start:
        raise SystemExit(f"{month}: nothing to train on before {month_start(month)}")

    train_data = load_dataset(
        db,
        start=start,
        end=train_end,
        horizon=args.horizon,
        label=args.label,
        exclude_st=True,
        benchmark=args.benchmark,
    )
    if len(train_data.dates) < args.min_train_days:
        return {
            "month": month,
            "skipped": f"only {len(train_data.dates)} training days (< {args.min_train_days})",
            "train_window": [train_data.dates[0].isoformat(), train_data.dates[-1].isoformat()],
            "rows": len(train_data),
            "factors": train_data.factors,
        }
    if len(train_data) < args.min_train_rows:
        return {
            "month": month,
            "skipped": f"only {len(train_data):,} training rows (< {args.min_train_rows:,})",
            "train_window": [train_data.dates[0].isoformat(), train_data.dates[-1].isoformat()],
            "rows": len(train_data),
            "factors": train_data.factors,
        }

    # An inner split so the run has a calibration number in addition to the live month.
    train_window, holdout_window = split_dates(train_data.dates, args.holdout)
    inner = Dataset(
        frame=train_data.frame[train_data.frame["trade_date"].isin(set(train_window))],
        factors=train_data.factors,
        dates=train_window,
    )
    try:
        model = build_model(
            inner, horizon=args.horizon, label=args.label, min_iv=args.min_iv, max_corr=args.max_corr
        )
    except SystemExit as exc:
        # "No factor reached IV ≥ …" means this window carries no signal, not that the run is broken.
        return {
            "month": month,
            "skipped": str(exc),
            "train_window": [train_data.dates[0].isoformat(), train_data.dates[-1].isoformat()],
            "rows": len(train_data),
            "factors": train_data.factors,
        }
    model["metrics"]["top_n"] = args.top_n
    model["trained_for_month"] = month
    model["train_window"] = [train_window[0].isoformat(), train_window[-1].isoformat()]

    # Out-of-sample on the target month — the same cross-section the simulation will use. A month
    # that has not finished yet has no forward returns, so it is trained but not scored.
    try:
        target = load_dataset(
            db,
            start=month_start(month),
            end=min(month_end(month), args.end or month_end(month)),
            horizon=args.horizon,
            label=args.label,
            exclude_st=True,
            factors=[factor["code"] for factor in model["factors"]],
            benchmark=args.benchmark,
        )
    except SystemExit as exc:
        return {
            "month": month,
            "skipped": f"trained, but the target month cannot be scored: {exc}",
            "train_window": [train_data.dates[0].isoformat(), train_data.dates[-1].isoformat()],
            "rows": len(train_data),
            "factors": train_data.factors,
        }
    metrics = {**model["metrics"], **evaluate_on_month(model, target.frame)}
    model["metrics"] = metrics
    model["dataset"] = {
        "name": args.dataset,
        "version": args.dataset_version,
        "sha256": args.dataset_sha256,
        "fingerprint": dataset_fingerprint(train_data, horizon=args.horizon, label=args.label),
    }

    out_dir = policy_dir(args.lookback_days, experiment=args.experiment)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{month}.json"
    path.write_text(json.dumps(model, indent=1, default=str))
    split_path = out_dir / f"{month}.split.json"
    split_path.write_text(
        json.dumps(
            {
                "train": [d.isoformat() for d in train_data.dates],
                "inner_train": [d.isoformat() for d in train_window],
                "inner_holdout": [d.isoformat() for d in holdout_window],
                "target_month": month,
            },
            indent=1,
        )
    )

    # Provenance: an experiment cites a dataset version, so the run carries it rather than a note.
    reference = dataset_reference(args.dataset, args.dataset_version) if args.dataset else None
    if reference:
        args.dataset_version = reference["version"]
        args.dataset_sha256 = reference["manifest_sha256"]
        print(
            f"   dataset  {reference['name']} v{reference['version']} "
            f"({reference['rows']:,} rows, {reference['date_from']} → {reference['date_to']})"
        )

    info = None
    if not args.no_mlflow:
        info = log_scorecard_run(
            model=model,
            params={
                "horizon": args.horizon,
                "label": args.label,
                "min_iv": args.min_iv,
                "max_corr": args.max_corr,
                "top_n": args.top_n,
                "train_start": train_data.dates[0].isoformat(),
                "train_end": train_data.dates[-1].isoformat(),
                "train_rows": len(train_data),
                "train_days": len(train_data.dates),
                "factors_available": len(train_data.factors),
                "factors_used": len(model["factors"]),
                "dataset": args.dataset or "",
                "dataset_version": args.dataset_version or "",
                "dataset_sha256": args.dataset_sha256 or "",
            },
            metrics=metrics,
            artifacts={"model.json": path, "split.json": split_path},
            target_month=month,
        )

    if info:
        model["mlflow"] = info
        model["mlflow_version"] = info["model_version"]
        path.write_text(json.dumps(model, indent=1, default=str))

    return {
        "month": month,
        # Relative to the policy directory: an absolute path is only valid on the machine that trained.
        "model_path": path.name,
        "train_window": model["train_window"],
        "train_rows": len(train_data),
        "train_days": len(train_data.dates),
        "factors_available": train_data.factors,
        "factors_used": [factor["code"] for factor in model["factors"]],
        "metrics": metrics,
        "mlflow": info,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--from", dest="month_from", required=True, help="first target month, YYYY-MM")
    parser.add_argument("--to", dest="month_to", required=True, help="last target month, YYYY-MM")
    parser.add_argument("--horizon", type=int, default=5)
    parser.add_argument("--label", choices=("relative", "absolute", "benchmark"), default="relative")
    parser.add_argument("--benchmark", default="000300.SH", help="index for the benchmark label")
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--min-iv", type=float, default=0.02)
    parser.add_argument("--max-corr", type=float, default=0.7)
    parser.add_argument("--holdout", type=float, default=0.2, help="inner validation share of the training window")
    parser.add_argument("--min-train-days", type=int, default=15)
    parser.add_argument("--min-train-rows", type=int, default=50_000)
    parser.add_argument("--start", type=date.fromisoformat, default=None, help="earliest training data (default 2026-01-05)")
    parser.add_argument(
        "--lookback-days", type=int, default=None, dest="lookback_days",
        help="trailing training window in calendar days (default: everything from --start)",
    )
    parser.add_argument("--end", type=date.fromisoformat, default=None, help="cap on the target month's last day")
    parser.add_argument("--dataset", default=None, help="openKMS file dataset name the slices came from")
    parser.add_argument("--dataset-version", type=int, default=None, dest="dataset_version")
    parser.add_argument("--dataset-sha256", default=None, dest="dataset_sha256")
    parser.add_argument("--no-mlflow", action="store_true", help="train and save locally only")
    parser.add_argument(
        "--experiment", default=None,
        help="suffix for the model directory, e.g. `bench20` — keeps two label variants apart",
    )
    args = parser.parse_args()

    db = SessionLocal()
    entries = []
    try:
        for month in next_months(args.month_from, args.month_to):
            print(f"\n== {month}", flush=True)
            entry = train_month(db, month, args)
            entries.append(entry)
            if entry.get("skipped"):
                print(
                    f"   skipped: {entry['skipped']} "
                    f"({entry['rows']:,} rows, {len(entry['factors'])} factors)",
                    flush=True,
                )
                continue
            metrics = entry["metrics"]
            print(
                f"   trained on {entry['train_window'][0]}…{entry['train_window'][1]} "
                f"({entry['train_rows']:,} rows, {entry['train_days']} days, "
                f"{len(entry['factors_used'])} factors)"
            )
            print(
                f"   {month}: AUC {metrics['target_month_auc']:.3f} · "
                f"top-{args.top_n} {metrics['target_month_picked_ret'] * 100:+.2f}% vs "
                f"universe {metrics['target_month_universe_ret'] * 100:+.2f}% "
                f"(excess {metrics['target_month_excess'] * 100:+.2f}%)"
            )
            if entry.get("mlflow"):
                print(
                    f"   MLflow run {entry['mlflow']['run_id'][:8]} · "
                    f"{MODEL_NAME} v{entry['mlflow']['model_version']}"
                )
    finally:
        db.close()

    out_dir = policy_dir(args.lookback_days, experiment=args.experiment)
    out_dir.mkdir(parents=True, exist_ok=True)
    index_path = out_dir / "index.json"
    previous = json.loads(index_path.read_text()) if index_path.exists() else {}
    for entry in entries:
        previous[entry["month"]] = entry
    index_path.write_text(json.dumps(previous, indent=1, default=str, sort_keys=True))
    trained = [e["month"] for e in entries if not e.get("skipped")]
    skipped = [e["month"] for e in entries if e.get("skipped")]
    print(f"\nindex → {index_path}")
    print(f"trained: {', '.join(trained) or '—'}")
    print(f"skipped: {', '.join(skipped) or '—'}")


if __name__ == "__main__":
    main()
