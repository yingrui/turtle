"""Push this app's writes back into the ontology.

Results and holdings are written here, not in openKMS — this app owns them. The ontology only needs
to *see* them, and its object reads come from the graph, so new rows are invisible until the affected
types are re-indexed. This module is that nudge, called after a simulation finishes and after a
portfolio change is applied.

One configuration list, not one per event: `STOCK_OPENKMS_REINDEX` names the object/link types that
mirror this app's data, and every write refreshes all of them. The alternative — a list per event —
drifts the moment a second writer appears, and re-indexing a handful of small types is cheap.

Best-effort by design: a callback that fails (openKMS down, key rotated) must never fail a write
that already succeeded. Unconfigured → no-op.
"""

from __future__ import annotations

import json
import logging
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Literal

from app.config import settings

logger = logging.getLogger(__name__)

CALLBACK_TIMEOUT_SECONDS = 10
TARGET_KINDS = ("object_type", "link_type")


@dataclass(frozen=True)
class ReindexTarget:
    kind: Literal["object_type", "link_type"]
    id: str

    @property
    def path(self) -> str:
        prefix = "object-types" if self.kind == "object_type" else "link-types"
        return f"/api/{prefix}/{self.id}/index-to-neo4j"


def reindex_targets() -> list[ReindexTarget]:
    """The configured targets, in order. Malformed entries are logged and skipped.

    A bad config must not take a request down: the write already succeeded, and a missing index
    refresh is a stale read, not a failed change.
    """
    raw = (settings.stock_openkms_reindex or "").strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("STOCK_OPENKMS_REINDEX is not valid JSON; skipping re-index")
        return []
    if not isinstance(parsed, list):
        logger.warning("STOCK_OPENKMS_REINDEX must be a JSON list; skipping re-index")
        return []
    targets: list[ReindexTarget] = []
    for entry in parsed:
        if not isinstance(entry, dict):
            logger.warning("STOCK_OPENKMS_REINDEX entry is not an object: %r", entry)
            continue
        kind = str(entry.get("kind") or "").strip()
        target_id = str(entry.get("id") or "").strip()
        if kind not in TARGET_KINDS or not target_id:
            logger.warning("STOCK_OPENKMS_REINDEX entry needs kind=%s and an id: %r", TARGET_KINDS, entry)
            continue
        targets.append(ReindexTarget(kind=kind, id=target_id))  # type: ignore[arg-type]
    return targets


def _post_index(targets: list[ReindexTarget]) -> None:
    base = settings.stock_openkms_base_url.rstrip("/")
    body = json.dumps({"neo4j_data_source_id": settings.stock_openkms_neo4j_data_source_id}).encode()
    for target in targets:
        request = urllib.request.Request(
            f"{base}{target.path}",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {settings.stock_openkms_api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=CALLBACK_TIMEOUT_SECONDS) as response:
                logger.info("openKMS re-index %s %s: %s", target.kind, target.id, response.status)
        except (urllib.error.URLError, OSError) as exc:
            logger.warning("openKMS re-index %s %s failed: %s", target.kind, target.id, exc)


def request_reindex() -> None:
    """Ask openKMS to re-index the mirrored types, off the request/job thread."""
    if not settings.openkms_index_configured:
        return
    targets = reindex_targets()
    if not targets:
        return
    threading.Thread(target=_post_index, args=(targets,), name="openkms-index", daemon=True).start()
