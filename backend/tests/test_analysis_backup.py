"""The artifact store must be recoverable: this project already lost one."""

import json
import tarfile
from pathlib import Path

from app.analysis.backup import main


def test_a_backup_records_every_file_with_its_digest(tmp_path):
    root = tmp_path / "rankings"
    (root / "regime" / "abc").mkdir(parents=True)
    (root / "regime" / "abc" / "scores.parquet").write_bytes(b"parquet-bytes")
    (root / "regime" / "abc" / "card.json").write_text('{"schema_version": 1}')
    destination = tmp_path / "backup"

    assert main(["--root", str(root), "--to", str(destination)]) == 0

    archives = list(destination.glob("*.tar.gz"))
    assert len(archives) == 1
    with tarfile.open(archives[0]) as archive:
        names = archive.getnames()
    assert any(name.endswith("scores.parquet") for name in names)

    manifest = json.loads((root / "backup-manifest.json").read_text())
    assert manifest["count"] == 2
    assert len(manifest["digest"]) == 64


def test_an_unchanged_store_produces_the_same_digest(tmp_path):
    root = tmp_path / "rankings"
    root.mkdir()
    (root / "a.txt").write_text("one")

    main(["--root", str(root), "--to", str(tmp_path / "b1")])
    first = json.loads((root / "backup-manifest.json").read_text())["digest"]
    main(["--root", str(root), "--to", str(tmp_path / "b2")])
    second = json.loads((root / "backup-manifest.json").read_text())["digest"]

    assert first == second


def test_a_missing_root_is_not_an_error(tmp_path):
    assert main(["--root", str(tmp_path / "nope"), "--to", str(tmp_path / "b")]) == 0
