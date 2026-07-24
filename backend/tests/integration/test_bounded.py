"""Integration tests for US3 — bounded autonomy, rollback, no-progress (T037)."""

from __future__ import annotations

from fastapi.testclient import TestClient

OBJECTIVE = (
    "Add idempotent order creation to POST /orders. Require an Idempotency-Key header. "
    "Do not modify the auth module."
)


def _start_bounded_run(client: TestClient, *, max_attempts: int) -> dict:
    create = client.post(
        "/api/runs",
        json={
            "workflow_id": "default-four-role-loop",
            "objective": OBJECTIVE,
            "repo_ref": "demo-repo",
            "budgets": {
                "max_attempts": max_attempts,
                "max_wall_clock_s": 3600,
                "max_model_calls": 20,
            },
        },
    )
    assert create.status_code == 201
    run_id = create.json()["id"]
    assert client.post(f"/api/runs/{run_id}/criteria:generate").status_code == 200
    assert client.post(f"/api/runs/{run_id}/criteria:approve").status_code == 200
    started = client.post(f"/api/runs/{run_id}:start")
    assert started.status_code == 200
    return started.json()


def test_exhaustion_rollback_and_undelivered_report(client_fail: TestClient) -> None:
    body = _start_bounded_run(client_fail, max_attempts=2)
    assert body["status"] == "EXHAUSTED"
    assert body["current_attempt"] == 2
    assert len(body["attempts"]) == 2
    assert body["undelivered_report"] is not None
    assert body["undelivered_report"]["delivered"] is False
    assert body["undelivered_report"]["reason"] == "max_attempts"
    second = body["attempts"][1]
    assert second["feedback"] is not None
    assert second["feedback"]["criterion"]
    assert second["feedback"]["failure_signature"]


def test_no_progress_stops_with_same_signature(
    client_no_progress: TestClient,
) -> None:
    body = _start_bounded_run(client_no_progress, max_attempts=5)
    assert body["status"] == "NO_PROGRESS"
    assert body["current_attempt"] == 2
    assert len(body["attempts"]) == 2
    assert body["undelivered_report"]["reason"] == "no_progress"
    sigs = [a["failure_signature"] for a in body["attempts"]]
    assert sigs[0] == sigs[1]
