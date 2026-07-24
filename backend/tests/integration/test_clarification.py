"""Integration tests for US4 — clarify, don't guess (T044)."""

from __future__ import annotations

from fastapi.testclient import TestClient

CONTRADICTORY_OBJECTIVE = (
    "return both 200 and 201 for the same successful request"
)


def _start_clarification_run(client: TestClient) -> dict:
    create = client.post(
        "/api/runs",
        json={
            "workflow_id": "default-four-role-loop",
            "objective": CONTRADICTORY_OBJECTIVE,
            "repo_ref": "demo-repo",
        },
    )
    assert create.status_code == 201
    run_id = create.json()["id"]
    assert client.post(f"/api/runs/{run_id}/criteria:generate").status_code == 200
    assert client.post(f"/api/runs/{run_id}/criteria:approve").status_code == 200
    started = client.post(f"/api/runs/{run_id}:start")
    assert started.status_code == 200
    return started.json()


def test_contradictory_criteria_clarification_required_no_attempt(
    client: TestClient,
) -> None:
    body = _start_clarification_run(client)
    assert body["status"] == "CLARIFICATION_REQUIRED"
    assert body["current_attempt"] == 0
    assert body["attempts"] == []
    clarification = body.get("clarification_request")
    assert clarification is not None
    assert clarification["reason"]
    assert clarification["message"]
    assert clarification["conflicts"]
    assert len(clarification["conflicts"]) >= 1
