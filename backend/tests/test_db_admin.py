"""The connection-release rule: what this app may terminate, and what it must never touch."""

from __future__ import annotations

import pytest


def test_only_idle_connections_of_this_app_past_the_grace_period_are_releasable():
    from app.services.db_admin_service import is_releasable

    def check(state, app, idle):
        return is_releasable(state=state, application_name=app, idle_seconds=idle)

    assert check("idle", "turtle-app", 120) is True
    assert check("idle", "turtle-market", 120) is True
    # Not idle: a query in flight, or a transaction left open — both would be destructive to end.
    assert check("active", "turtle-app", 120) is False
    assert check("idle in transaction", "turtle-app", 120) is False
    # Not ours: MLflow and Keycloak share the server.
    assert check("idle", "mlflow", 9999) is False
    assert check("idle", "", 9999) is False
    # Too fresh: it may be a pooled connection about to be reused.
    assert check("idle", "turtle-app", 5) is False
    # The connection serving the report itself is never a candidate (see `report`/`release_idle`).


def test_the_grace_period_is_configurable():
    from app.services.db_admin_service import is_releasable

    assert (
        is_releasable(state="idle", application_name="turtle-app", idle_seconds=5, min_idle_seconds=0)
        is True
    )


@pytest.mark.parametrize("app_name", ["turtle-app", "turtle-market"])
def test_both_of_this_processes_pools_are_covered(app_name):
    """`uvicorn --reload` owns two pools; releasing only one leaves the other half holding slots."""
    from app.services.db_admin_service import is_releasable

    assert is_releasable(state="idle", application_name=app_name, idle_seconds=600, min_idle_seconds=60)
