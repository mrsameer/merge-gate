"""T021 [US1] Integration test — the happy-path loop end to end.

Exercises User Story 1's independent test:

    objective -> hybrid contract -> human approval -> isolated execution
    -> deterministic verdict -> final human gate -> SUCCESS

and asserts the core integrity claim: the verdict is produced by the separate
acceptance engine (its inputs are files / commands / exit codes), never by the
coding agent. Written FIRST and MUST FAIL until the loop is wired (T022-T029).
"""

from __future__ import annotations

import time

import pytest

# Terminal states that mean the run is finished (FR-025).
TERMINAL_STATES = {
    "SUCCESS",
    "CLARIFICATION_REQUIRED",
    "HUMAN_REJECTED",
    "EXHAUSTED",
    "NO_PROGRESS",
    "TIMED_OUT",
    "POLICY_BLOCKED",
    "CANCELLED",
}


def _poll_until(client, run_id, predicate, timeout_s: float = 90.0):
    """Poll GET /runs/{id} until `predicate(body)` is true or timeout."""
    deadline = time.time() + timeout_s
    body: dict = {}
    while time.time() < deadline:
        response = client.get(f"/api/runs/{run_id}")
        assert response.status_code == 200, response.text
        body = response.json()
        if predicate(body):
            return body
        time.sleep(0.5)
    pytest.fail(f"timed out waiting on run {run_id}; last state: {body!r}")


def test_happy_path_objective_to_success(client, workflow_id, demo_repo, objective):
    """Full loop: objective through to a SUCCESS verdict and mergeable branch."""
    # 1. Create the run against the real demo repo.
    created = client.post(
        "/api/runs",
        json={
            "workflow_id": workflow_id,
            "objective": objective,
            "repo_ref": str(demo_repo),
            "budgets": {
                "max_attempts": 3,
                "max_wall_clock_s": 300,
                "max_model_calls": 20,
            },
        },
    )
    assert created.status_code == 201, created.text
    run_id = created.json()["id"]

    # 2. Generate the hybrid contract; criteria must be grounded in real files.
    generated = client.post(
        f"/api/runs/{run_id}/criteria:generate", json={"mode": "hybrid"}
    )
    assert generated.status_code == 200, generated.text
    contract = generated.json()
    assert contract["criteria"], "expected at least one generated criterion"

    # 3. Human approves and freezes the contract before any code is written.
    approved = client.post(f"/api/runs/{run_id}/criteria:approve")
    assert approved.status_code == 200, approved.text
    assert approved.json()["approved"] is True

    # 4. Start the run.
    started = client.post(f"/api/runs/{run_id}:start")
    assert started.status_code in (200, 202), started.text

    # 5. Run proceeds to the final merge gate (validation passed).
    at_final_gate = _poll_until(
        client,
        run_id,
        lambda b: b["status"] == "awaiting_gate" and b.get("current_attempt", 0) >= 1,
    )
    assert at_final_gate["status"] == "awaiting_gate"

    # 6. Approve the final gate -> SUCCESS with a mergeable branch/patch ref.
    final = client.post(f"/api/runs/{run_id}/gate:approve")
    assert final.status_code == 200, final.text

    done = _poll_until(client, run_id, lambda b: b["status"] in TERMINAL_STATES)
    assert done["status"] == "SUCCESS", done
    assert done.get("branch") or done.get("patch_ref"), "expected mergeable result"


def test_verdict_comes_from_acceptance_engine_not_the_agent(
    client, workflow_id, demo_repo, objective
):
    """The verdict's inputs are files/commands/exit-codes, not a model response.

    This is the crux of Principle I: acceptance is computed by a separate
    deterministic engine. We assert the recorded verdict exposes an ordered
    check pipeline with real exit codes and an acceptance hash — evidence that
    the decision was computed, not asserted by the coding agent.
    """
    created = client.post(
        "/api/runs",
        json={
            "workflow_id": workflow_id,
            "objective": objective,
            "repo_ref": str(demo_repo),
            "budgets": {
                "max_attempts": 3,
                "max_wall_clock_s": 300,
                "max_model_calls": 20,
            },
        },
    )
    assert created.status_code == 201, created.text
    run_id = created.json()["id"]

    assert (
        client.post(
            f"/api/runs/{run_id}/criteria:generate", json={"mode": "hybrid"}
        ).status_code
        == 200
    )
    assert client.post(f"/api/runs/{run_id}/criteria:approve").status_code == 200
    assert client.post(f"/api/runs/{run_id}:start").status_code in (200, 202)

    _poll_until(
        client,
        run_id,
        lambda b: (
            b.get("current_attempt", 0) >= 1
            and b["status"] in (TERMINAL_STATES | {"awaiting_gate"})
        ),
    )

    attempts = client.get(f"/api/runs/{run_id}/attempts")
    assert attempts.status_code == 200, attempts.text
    entries = attempts.json()
    assert entries, "expected at least one attempt with a verdict"

    verdict = entries[0]["verdict"]
    assert "passed" in verdict
    assert verdict.get("acceptance_hash"), "verdict must carry an acceptance hash"

    checks = verdict["checks"]
    assert checks, "verdict must record an ordered check pipeline"
    for check in checks:
        # Deterministic evidence: every check has a command exit code + step.
        assert "exit_code" in check
        assert check["step"] in {
            "build",
            "lint",
            "existing_tests",
            "new_tests",
            "migration",
            "coverage",
            "api_contract",
            "policy",
        }


def test_exception_never_classified_as_success(
    client, workflow_id, demo_repo, objective
):
    """A crash/timeout must map to a safe stop, never SUCCESS (Principle IV)."""
    created = client.post(
        "/api/runs",
        json={
            "workflow_id": workflow_id,
            "objective": objective,
            "repo_ref": str(demo_repo),
            # A zero wall-clock budget forces an immediate bounded stop.
            "budgets": {
                "max_attempts": 1,
                "max_wall_clock_s": 0,
                "max_model_calls": 1,
            },
        },
    )
    assert created.status_code == 201, created.text
    run_id = created.json()["id"]

    client.post(f"/api/runs/{run_id}/criteria:generate", json={"mode": "hybrid"})
    client.post(f"/api/runs/{run_id}/criteria:approve")
    client.post(f"/api/runs/{run_id}:start")

    done = _poll_until(client, run_id, lambda b: b["status"] in TERMINAL_STATES)
    assert done["status"] != "SUCCESS"
    assert done["status"] in {"TIMED_OUT", "NO_PROGRESS", "EXHAUSTED", "CANCELLED"}
