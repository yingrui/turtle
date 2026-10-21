"""Push finished simulation runs back into the ontology.

Results are written here, not in openKMS — this app owns the backtest. The ontology only needs to
*see* them, and its object reads come from the graph, so a finished run must be re-indexed before
`(:Simulation)-[:simulationOf]->(:Portfolio)` shows it. This is that nudge.

Best-effort by design: a callback that fails (openKMS down, key rotated) must never fail a
simulation that already succeeded. Unconfigured → no-op.
"""

from __future__ import annotations

import json
import logging
import threading
import urllib.error
import urllib.request

from app.config import settings

logger = logging.getLogger(__name__)

CALLBACK_TIMEOUT_SECONDS = 10


def _post_index() -> None:
    """Re-index the Simulation nodes *and* the `simulationOf` edges they hang from.

    Indexing only the object type leaves a new run as a floating node: the edge comes from the
    link indexer, so both are requested.
    """
    base = settings.stock_openkms_base_url.rstrip("/")
    body = json.dumps({"neo4j_data_source_id": settings.stock_openkms_neo4j_data_source_id}).encode()
    targets = (
        f"/api/object-types/{settings.stock_openkms_simulation_type_id}/index-to-neo4j",
        f"/api/link-types/{settings.stock_openkms_simulation_link_type_id}/index-to-neo4j",
    )
    for path in targets:
        request = urllib.request.Request(
            f"{base}{path}",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {settings.stock_openkms_api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=CALLBACK_TIMEOUT_SECONDS) as response:
                logger.info("openKMS re-index %s: %s", path, response.status)
        except (urllib.error.URLError, OSError) as exc:
            logger.warning("openKMS re-index %s failed: %s", path, exc)


def notify_simulation_indexed() -> None:
    """Ask openKMS to re-index Simulation objects, off the job thread."""
    if not settings.openkms_index_configured:
        return
    threading.Thread(target=_post_index, name="openkms-index", daemon=True).start()
