"""Copy the artifact store somewhere that survives the volume.

Rankings live on a PVC. A PVC survives a pod restart but not a lost node, and this project has already
lost one artifact store (the dataset objects in MinIO) — the sources kept their `row_count` and their
sha256 and pointed at nothing. A backup makes that failure recoverable instead of fatal.

    python -m app.analysis.backup --to s3://openkms/rankings-backup   # or --to /var/backups/rankings

The tarball is named by the manifest digest, so an unchanged store does not produce a new object.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import tarfile
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path


def _manifest(root: Path) -> tuple[dict, str]:
    entries = []
    for path in sorted(root.rglob("*")):
        # The manifest lives in the store; hashing it would make every backup differ from the last.
        if path.is_file() and path.name != "backup-manifest.json":
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            entries.append({"path": str(path.relative_to(root)), "sha256": digest, "size": path.stat().st_size})
    payload = json.dumps(entries, sort_keys=True)
    return {"files": entries, "count": len(entries)}, hashlib.sha256(payload.encode()).hexdigest()


def _tarball(root: Path) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        archive.add(root, arcname=root.name)
    return buffer.getvalue()


def _upload(target: str, name: str, blob: bytes) -> str:
    if not target.startswith("s3://"):
        destination = Path(target) / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(blob)
        return str(destination)
    parsed = urllib.parse.urlparse(target)
    bucket = parsed.netloc
    prefix = parsed.path.strip("/")
    import boto3  # imported lazily: a local backup must work without it

    client = boto3.client(
        "s3",
        endpoint_url=os.environ.get("BACKUP_S3_ENDPOINT") or os.environ.get("MLFLOW_S3_ENDPOINT_URL"),
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    )
    key = f"{prefix}/{name}" if prefix else name
    client.put_object(Bucket=bucket, Key=key, Body=blob)
    return f"s3://{bucket}/{key}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=os.environ.get("STOCK_RANKINGS_DIR", "reports/rankings"))
    parser.add_argument("--to", required=True, help="directory or s3://bucket/prefix")
    args = parser.parse_args(argv)

    root = Path(args.root)
    if not root.exists():
        print(f"nothing to back up: {root} does not exist")
        return 0
    manifest, digest = _manifest(root)
    name = f"rankings-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{digest[:12]}.tar.gz"
    location = _upload(args.to, name, _tarball(root))
    (root / "backup-manifest.json").write_text(json.dumps({**manifest, "digest": digest}, indent=2))
    print(f"backed up {manifest['count']} files ({digest[:12]}) → {location}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
