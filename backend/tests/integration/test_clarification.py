"""T044 [US4] — contradictory criteria halt before execution.

The saved demo contradiction must be detected after the contract is frozen
but before baseline validation, worktree creation, or harness execution.  The
response is deliberately asserted through the public API so this test covers
the detector, terminal transition, structured payload, and zero-attempt
guarantee together.
"""

from __future__ import annotations


def test_contradictory_contract_requires_clarification_without_an_attempt(
    client, workflow_id, demo_repo, contradictory_objective
) -> None:
    created = client.post(
        "/api/runs",
        json={
            "workflow_id": workflow_id,
            "objective": contradictory_objective,
            "repo_ref": str(demo_repo),
            "provider": "scripted",
            "budgets": {
                "max_attempts": 3,
                "max_wall_clock_s": 300,
                "max_model_calls": 20,
            },
        },
    )
    assert created.status_code == 201, created.text
    run_id = created.json()["id"]

    generated = client.post(
        f"/api/runs/{run_id}/criteria:generate", json={"mode": "hybrid"}
    )
    assert generated.status_code == 200, generated.text
    approved = client.post(f"/api/runs/{run_id}/criteria:approve")
    assert approved.status_code == 200, approved.text

    started = client.post(f"/api/runs/{run_id}:start")

    assert started.status_code == 200, started.text
    body = started.json()
    assert body["status"] == "CLARIFICATION_REQUIRED"
    assert body["current_attempt"] == 0
    assert body["attempts"] == []
    assert body["cost"]["model_calls"] == 0
    assert body["clarification"]["conflicting_criteria"] == ["feature-exists"]
    assert "200" in body["clarification"]["reason"]
    assert "201" in body["clarification"]["reason"]

    attempts = client.get(f"/api/runs/{run_id}/attempts")
    assert attempts.status_code == 200, attempts.text
    assert attempts.json() == []


def test_non_contradictory_contract_is_not_misclassified(
    client, workflow_id, demo_repo, objective
) -> None:
    created = client.post(
        "/api/runs",
        json={
            "workflow_id": workflow_id,
            "objective": objective,
            "repo_ref": str(demo_repo),
            "provider": "scripted",
            "budgets": {
                "max_attempts": 3,
                "max_wall_clock_s": 300,
                "max_model_calls": 20,
            },
        },
    )
    run_id = created.json()["id"]
    client.post(f"/api/runs/{run_id}/criteria:generate", json={"mode": "hybrid"})
    client.post(f"/api/runs/{run_id}/criteria:approve")

    started = client.post(f"/api/runs/{run_id}:start")

    assert started.status_code == 202, started.text
    assert started.json()["status"] != "CLARIFICATION_REQUIRED"
