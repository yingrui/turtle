"""Export one month of the training panel and register it as a file-dataset version.

The training set is a **frozen query** — factor values, forward returns and the label, materialised
into a parquet slice. Nothing here joins at read time: the join happens once, here, and the result is
an immutable file that a model can be pinned to.

    cd backend
    python -m scripts.export_training_set --month 2026-09
    python -m scripts.export_training_set --start 2026-06-01 --end 2026-09-30 --version 3

Without `--version` the script opens a draft, adds the slice, and leaves it a draft for a human to
publish; with `--version` it appends to that existing draft. `--publish` freezes it in the same run,
which is what a nightly-ish job would do once the slice is verified.

Where the data goes is the openKMS Catalog (`OPENKMS_API_BASE` + `OPENKMS_API_KEY`, or the skill's
config), because the dataset needs an identity the training run can record in MLflow:

    dataset=scorecard-training-5d  version=1  file=2026-09.parquet  sha256=…
"""

from __future__ import annotations

import argparse
import io
import json
import os
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from scripts.scorecard import load_dataset

DEFAULT_DATASET_NAME = "scorecard-training-5d"
SKILL_CONFIG = Path.home() / ".pi" / "agent" / "skills" / "openkms" / "config.yml"


# --- openKMS ----------------------------------------------------------------------------


def _api() -> tuple[str, str]:
    """Base URL and key from the environment, falling back to the skill's config."""
    base = os.environ.get("OPENKMS_API_BASE")
    key = os.environ.get("OPENKMS_API_KEY")
    if base and key:
        return base.rstrip("/"), key
    if SKILL_CONFIG.exists():
        values = {}
        for line in SKILL_CONFIG.read_text().splitlines():
            if ":" in line and not line.startswith(" "):
                name, _, value = line.partition(":")
                values[name.strip()] = value.strip().strip('"')
        if values.get("api_base_url") and values.get("api_key"):
            return values["api_base_url"].rstrip("/"), values["api_key"]
    raise SystemExit(
        "openKMS credentials missing: set OPENKMS_API_BASE and OPENKMS_API_KEY "
        f"(or configure {SKILL_CONFIG})"
    )


def _request(method: str, path: str, *, body: bytes | None = None, headers: dict | None = None) -> dict:
    base, key = _api()
    request = urllib.request.Request(
        f"{base}/api{path}",
        method=method,
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            raw = response.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"{method} {path} → {exc.code}: {exc.read().decode()[:400]}") from exc


def find_or_create_dataset(name: str) -> dict:
    datasets = _request("GET", "/datasets?kind=file")["items"]
    for dataset in datasets:
        if dataset["display_name"] == name:
            return dataset
    return _request("POST", "/datasets", body=json.dumps({"kind": "file", "display_name": name}).encode())


def upload_slice(dataset_id: str, version: int, filename: str, payload: bytes) -> dict:
    base, key = _api()
    boundary = "----openkms" + datetime.now().strftime("%H%M%S%f")
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + payload + f"\r\n--{boundary}--\r\n".encode()
    request = urllib.request.Request(
        f"{base}/api/dataset-versions/{dataset_id}/{version}/files",
        method="POST",
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"upload → {exc.code}: {exc.read().decode()[:400]}") from exc


# --- the slice --------------------------------------------------------------------------


def build_slice(
    db, *, start: date, end: date, horizon: int, label: str, benchmark: str | None = None
) -> pd.DataFrame:
    """The training panel for a window: ranks, forward return, label — one row per stock per day."""
    data = load_dataset(
        db, start=start, end=end, horizon=horizon, label=label, benchmark=benchmark
    )
    frame = data.frame.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.date
    return frame.sort_values(["trade_date", "ts_code"])


def month_bounds(month: str) -> tuple[date, date]:
    first = date.fromisoformat(f"{month}-01")
    next_month = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
    return first, next_month - timedelta(days=1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--month", default=None, help="YYYY-MM — export that month")
    parser.add_argument("--start", type=date.fromisoformat, default=None)
    parser.add_argument("--end", type=date.fromisoformat, default=None)
    parser.add_argument("--horizon", type=int, default=5)
    parser.add_argument("--label", choices=("relative", "absolute", "benchmark"), default="relative")
    parser.add_argument("--benchmark", default="000300.SH", help="index for the benchmark label")
    parser.add_argument("--dataset", default=DEFAULT_DATASET_NAME, help="file dataset name in openKMS")
    parser.add_argument("--version", type=int, default=None, help="append to this draft (default: open a new one)")
    parser.add_argument("--publish", action="store_true", help="publish the version after uploading")
    parser.add_argument("--notes", default=None)
    parser.add_argument("--out", default=None, help="also keep the parquet locally")
    args = parser.parse_args()

    if args.month:
        start, end = month_bounds(args.month)
        filename = f"{args.month}.parquet"
    elif args.start and args.end:
        start, end = args.start, args.end
        filename = f"{start.isoformat()}_{end.isoformat()}.parquet"
    else:
        raise SystemExit("give --month YYYY-MM or --start/--end")

    from app.database import SessionLocal

    db = SessionLocal()
    try:
        frame = build_slice(
            db,
            start=start,
            end=end,
            horizon=args.horizon,
            label=args.label,
            benchmark=args.benchmark,
        )
    finally:
        db.close()
    if frame.empty:
        raise SystemExit(f"no rows for {start}…{end} — compute the factors first")

    buffer = io.BytesIO()
    frame.to_parquet(buffer, index=False)
    payload = buffer.getvalue()
    if args.out:
        Path(args.out).write_bytes(payload)

    dataset = find_or_create_dataset(args.dataset)
    if args.version is None:
        version = _request(
            "POST",
            f"/dataset-versions/{dataset['id']}",
            body=json.dumps(
                {
                    "notes": args.notes
                    or f"{start.isoformat()}…{end.isoformat()} · horizon {args.horizon} · {args.label}"
                }
            ).encode(),
        )
        version_number = version["version"]
    else:
        version_number = args.version

    saved = upload_slice(dataset["id"], version_number, filename, payload)
    print(
        f"{filename}: {len(frame):,} rows · {len(payload) / 1024:.0f} KB · "
        f"sha256 {saved['sha256'][:12]}… · date range {saved['date_from']}…{saved['date_to']}"
    )
    print(f"dataset {dataset['display_name']} ({dataset['id']}) · v{version_number}")

    if args.publish:
        published = _request("POST", f"/dataset-versions/{dataset['id']}/{version_number}/publish")
        print(f"published v{published['version']}: {published['file_count']} file(s), {published['row_count']:,} rows")
    else:
        print(
            "still a draft — publish it when verified: "
            f"POST /api/dataset-versions/{dataset['id']}/{version_number}/publish"
        )

    print(
        "record this in the training run: "
        + json.dumps(
            {
                "dataset": args.dataset,
                "version": version_number,
                "file": filename,
                "sha256": saved["sha256"],
            }
        )
    )


if __name__ == "__main__":
    main()
