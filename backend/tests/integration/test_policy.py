"""Integration tests for US5 — anti-cheat policy enforcement (T048)."""

from __future__ import annotations

from fastapi.testclient import TestClient

OBJECTIVE = (
    "Add idempotent order creation to POST /orders. Require an Idempotency-Key header. "
    "Do not modify the auth module."
)


def _start_policy_run(client: TestClient) -> dict:
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
    return started.json()


def test_protected_path_edit_policy_blocked(client_policy_auth: TestClient) -> None:
    body = _start_policy_run(client_policy_auth)
    assert body["status"] == "POLICY_BLOCKED"
    assert body["current_attempt"] == 1
    assert len(body["attempts"]) == 1
    assert body["attempts"][0]["verdict"] is None
    violation = body.get("policy_violation")
    assert violation is not None
    assert violation["kind"] == "protected_path"
    assert "app/auth" in violation["offender"]


def test_forbidden_diff_pattern_policy_blocked(client_policy_skip: TestClient) -> None:
    body = _start_policy_run(client_policy_skip)
    assert body["status"] == "POLICY_BLOCKED"
    assert body["current_attempt"] == 1
    violation = body.get("policy_violation")
    assert violation is not None
    assert violation["kind"] == "forbidden_pattern"
    assert "pytest.mark.skip" in violation["offender"]
