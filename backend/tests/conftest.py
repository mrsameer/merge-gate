"""Shared pytest fixtures for MergeGate backend tests.

These fixtures wire the FastAPI control plane (T010, `mergegate.api.main:app`)
to a `TestClient` so contract and integration tests can exercise the REST
surface described in `specs/001-mergegate-control-plane/contracts/control-plane-api.md`.

Until the app and its routers exist, importing `mergegate.api.main` fails and
every dependent test errors — the intended red state for the TDD tasks
(T020 contract, T021 integration happy-path).
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Repository root is two levels up: <root>/backend/tests/conftest.py
REPO_ROOT = Path(__file__).resolve().parents[2]

# The self-contained demo repo fixture is the target of every run (plan.md).
DEMO_REPO = REPO_ROOT / "demo-repo"

# The seed objective from spec.md "Assumptions": idempotent order creation.
IDEMPOTENT_ORDER_OBJECTIVE = (
    "Make POST /orders idempotent: require an Idempotency-Key header; the same "
    "key with the same body returns the original order and creates no new row; "
    "the same key with a different body returns HTTP 409. Add tests and OpenAPI "
    "docs. Do not modify the auth module."
)

# A deliberately self-contradictory objective for the clarification path (US4).
CONTRADICTORY_OBJECTIVE = (
    "POST /orders must return both 200 and 201 for the same successful request."
)


@pytest.fixture()
def demo_repo() -> Path:
    """Filesystem path to the demo-repo fixture targeted by every run."""
    return DEMO_REPO


@pytest.fixture()
def objective() -> str:
    """The seed idempotent-order objective from spec.md."""
    return IDEMPOTENT_ORDER_OBJECTIVE


@pytest.fixture()
def contradictory_objective() -> str:
    """The saved impossible objective used by the US4 clarification demo."""
    return CONTRADICTORY_OBJECTIVE


@pytest.fixture()
def app():
    """The FastAPI application under test.

    Imported lazily inside the fixture so collection errors surface as test
    failures rather than import-time crashes across the whole suite.
    """
    from mergegate.api.main import app as fastapi_app

    return fastapi_app


@pytest.fixture()
def client(app):
    """A FastAPI `TestClient` bound to the control-plane app."""
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def workflow_id(client) -> str:
    """Create the default four-role-loop workflow and return its id."""
    response = client.post(
        "/api/workflows",
        json={"name": "MergeGate default loop", "template": "four_role_loop"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.fixture()
def run_id(client, workflow_id) -> str:
    """Create a run against the demo repo with the seed objective.

    Per the contract, a freshly created run is at the contract gate
    (`status == "awaiting_gate"`, `current_attempt == 0`) and no code has run.
    """
    response = client.post(
        "/api/runs",
        json={
            "workflow_id": workflow_id,
            "objective": IDEMPOTENT_ORDER_OBJECTIVE,
            "repo_ref": str(DEMO_REPO),
            "budgets": {
                "max_attempts": 3,
                "max_wall_clock_s": 300,
                "max_model_calls": 20,
            },
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.fixture()
def approved_run_id(client, run_id) -> str:
    """A run whose hybrid contract has been generated and approved (frozen)."""
    generated = client.post(
        f"/api/runs/{run_id}/criteria:generate", json={"mode": "hybrid"}
    )
    assert generated.status_code == 200, generated.text

    approved = client.post(f"/api/runs/{run_id}/criteria:approve")
    assert approved.status_code == 200, approved.text
    return run_id
