"""Integration test: objective → contract → run → SUCCESS (T021)."""

from __future__ import annotations

from fastapi.testclient import TestClient

OBJECTIVE = (
    "Add idempotent order creation to POST /orders. Require an Idempotency-Key header. "
    "Do not modify the auth module."
)


def test_happy_path_objective_to_success(client: TestClient) -> None:
    create = client.post(
        "/api/runs",
        json={
            "workflow_id": "default-four-role-loop",
            "objective": OBJECTIVE,
            "repo_ref": "demo-repo",
        },
    )
    assert create.status_code == 201
    run_id = create.json()["id"]

    assert client.post(f"/api/runs/{run_id}/criteria:generate").status_code == 200
    assert client.post(f"/api/runs/{run_id}/criteria:approve").status_code == 200

    started = client.post(f"/api/runs/{run_id}:start")
    assert started.status_code == 200
    body = started.json()
    assert body["current_attempt"] == 1
    assert body["attempts"][0]["verdict"]["passed"] is True
    assert body["attempts"][0]["verdict"]["acceptance_hash"]
    assert body["status"] == "awaiting_final_gate"

    finished = client.post(f"/api/runs/{run_id}/gate:approve")
    assert finished.status_code == 200
    assert finished.json()["status"] == "SUCCESS"
    assert finished.json()["branch_ref"]
