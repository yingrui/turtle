"""Ops view of the database's connection budget, and a way to release what this app is holding.

The deployment's PostgreSQL is shared (MLflow, Keycloak, openKMS) with `max_connections = 100`, and
`uvicorn --reload` builds every pool twice (supervisor + worker). When the server runs out, requests
fail with `remaining connection slots are reserved for non-replication superuser connections` — a
message that says nothing about which process is at fault.

Two things are deliberately conservative here:

- **Only this app's connections.** The filter is `application_name IN ('turtle-app', 'turtle-market')`,
  so an ops click can never kill MLflow mid-run.
- **Only idle ones, and only after a grace period.** `state = 'idle'` excludes anything mid-query and
  anything sitting in an open transaction; the grace period avoids grabbing a connection that was
  just returned to the pool and is about to be reused.
"""

from __future__ import annotations

from sqlalchemy import text

from app.core.configurer import get_connection_pool

#: Every pool this process owns, by `application_name`.
OWN_APPS = ("turtle-app", "turtle-market")

#: Default grace period: a connection idle for less than this may still be in the pool's reuse path.
DEFAULT_MIN_IDLE_SECONDS = 60


def is_releasable(
    *,
    state: str | None,
    application_name: str | None,
    idle_seconds: float | None,
    apps: tuple[str, ...] = OWN_APPS,
    min_idle_seconds: int = DEFAULT_MIN_IDLE_SECONDS,
) -> bool:
    """Whether one backend may be terminated by this app. Pure, so the rule is testable."""
    if state != "idle":
        return False
    if application_name not in apps:
        return False
    return idle_seconds is not None and idle_seconds >= min_idle_seconds


def _rows(db) -> list[dict]:
    rows = db.execute(
        text(
            "SELECT pid, coalesce(application_name, '') AS application_name, state, "
            "       extract(epoch FROM now() - coalesce(state_change, backend_start)) AS age, "
            "       pid = pg_backend_pid() AS is_self "
            "FROM pg_stat_activity "
            "WHERE backend_type = 'client backend'"
        )
    ).all()
    return [
        {
            "pid": row[0],
            "application_name": row[1],
            "state": row[2],
            "idle_seconds": None if row[3] is None else float(row[3]),
            #: The connection serving this very request: counted, never a termination candidate.
            "is_self": bool(row[4]),
        }
        for row in rows
    ]


def report(db, *, min_idle_seconds: int = DEFAULT_MIN_IDLE_SECONDS) -> dict:
    """Who is holding connections right now, and which of them this app may release."""
    max_connections = int(db.execute(text("SHOW max_connections")).scalar() or 0)
    reserved = int(db.execute(text("SHOW superuser_reserved_connections")).scalar() or 0)
    rows = _rows(db)

    by_app: dict[tuple[str, str], dict] = {}
    for row in rows:
        key = (row["application_name"] or "(unnamed)", row["state"] or "?")
        entry = by_app.setdefault(
            key, {"application_name": key[0], "state": key[1], "count": 0, "oldest_idle_seconds": None}
        )
        entry["count"] += 1
        if row["state"] == "idle" and row["idle_seconds"] is not None:
            current = entry["oldest_idle_seconds"]
            entry["oldest_idle_seconds"] = max(current or 0, row["idle_seconds"])

    own = [r for r in rows if r["application_name"] in OWN_APPS]
    releasable = [
        r
        for r in rows
        if not r["is_self"]
        and is_releasable(
            state=r["state"],
            application_name=r["application_name"],
            idle_seconds=r["idle_seconds"],
            min_idle_seconds=min_idle_seconds,
        )
    ]
    return {
        "max_connections": max_connections,
        "superuser_reserved": reserved,
        #: Non-superusers only see their own backends in `pg_stat_activity`, so this is "connections
        #: this app can see", not the server's total — the UI says so.
        "visible_scope": "own",
        "in_use": len(rows),
        "by_app": sorted(by_app.values(), key=lambda entry: -entry["count"]),
        "this_app": {
            "connections": len(own),
            "idle": sum(1 for r in own if r["state"] == "idle"),
            "releasable": len(releasable),
        },
        "min_idle_seconds": min_idle_seconds,
    }


def release_idle(db, *, min_idle_seconds: int = DEFAULT_MIN_IDLE_SECONDS) -> dict:
    """Terminate this app's idle backends, then drop this process's pools so they stop holding any.

    Terminating is enough for the server to reclaim the slot; disposing the pools additionally clears
    the *other* half of a `--reload` process pair, which is usually the one nobody remembers.
    """
    rows = _rows(db)
    targets = [
        r["pid"]
        for r in rows
        if not r["is_self"]
        and is_releasable(
            state=r["state"],
            application_name=r["application_name"],
            idle_seconds=r["idle_seconds"],
            min_idle_seconds=min_idle_seconds,
        )
    ]
    terminated = 0
    if targets:
        terminated = int(
            db.execute(
                text(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE pid = ANY(:pids) AND pg_terminate_backend(pid)"
                ),
                {"pids": targets},
            ).scalar()
            or 0
        )

    # Local pools: close what this process is holding so the next request opens fresh connections.
    from app.database import engine

    engine.dispose()
    get_connection_pool().dispose()

    return {
        "terminated": terminated,
        "candidates": len(targets),
        "pools_disposed": ["turtle-app", "turtle-market"],
        "after": report(db, min_idle_seconds=min_idle_seconds),
    }
