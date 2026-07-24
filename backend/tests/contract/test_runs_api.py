"""T020 [US1] Contract tests for the runs / criteria / start API surface.

Encodes the interface promised by
`specs/001-mergegate-control-plane/contracts/control-plane-api.md` for:

    POST /api/runs                              (create a run)
    GET  /api/runs/{id}                         (run status)
    POST /api/runs/{id}/criteria:generate       (hybrid criteria generation)
    PUT  /api/runs/{id}/criteria                (edit/prioritize before approval)
    POST /api/runs/{id}/criteria:approve        (freeze the contract)
    POST /api/runs/{id}:start                   (begin execution after approval)

These are written FIRST and MUST FAIL until the API is implemented (T028).
The central integrity claim under test is *contract-before-code*: a run cannot
start until a human has approved and frozen the contract.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# POST /api/runs — create a run
# ---------------------------------------------------------------------------


def test_create_run_returns_201_awaiting_contract_gate(client, workflow_id, objective):
    """A newly created run sits at the contract gate with no attempts yet."""
    response = client.post(
        "/api/runs",
        json={
            "workflow_id": workflow_id,
            "objective": objective,
            "repo_ref": "demo-repo",
            "budgets": {
                "max_attempts": 3,
                "max_wall_clock_s": 300,
                "max_model_calls": 20,
            },
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "awaiting_gate"
    assert body["current_attempt"] == 0
    assert body["objective"] == objective
    assert body["workflow_id"] == workflow_id
    assert "id" in body


def test_create_run_preserves_explicit_provider_and_model(
    client, workflow_id, objective
):
    response = client.post(
        "/api/runs",
        json={
            "workflow_id": workflow_id,
            "objective": objective,
            "repo_ref": "demo-repo",
            "provider": "gemini",
            "model": "gemini-2.5-pro",
            "budgets": {
                "max_attempts": 3,
                "max_wall_clock_s": 300,
                "max_model_calls": 20,
            },
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["provider"] == "gemini"
    assert response.json()["model"] == "gemini-2.5-pro"


def test_ui_default_workflow_is_available_without_a_prior_workflow_request(
    client, objective
):
    """A freshly opened UI can create its first run against its default graph."""
    response = client.post(
        "/api/runs",
        json={
            "workflow_id": "default-four-role-loop",
            "objective": objective,
            "repo_ref": "demo-repo",
            "provider": "scripted",
            "budgets": {
                "max_attempts": 3,
                "max_wall_clock_s": 300,
                "max_model_calls": 20,
            },
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["workflow_id"] == "default-four-role-loop"
    generated = client.post(
        f"/api/runs/{response.json()['id']}/criteria:generate", json={"mode": "hybrid"}
    )
    assert generated.status_code == 200, generated.text


def test_get_run_returns_status_and_cost(client, run_id):
    """GET /runs/{id} exposes status, attempt counter, and cost accounting."""
    response = client.get(f"/api/runs/{run_id}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == run_id
    assert body["status"] == "awaiting_gate"
    assert body["current_attempt"] == 0
    # Cost accounting is present from creation (FR-022), zeroed before any run.
    assert "cost" in body
    assert body["cost"]["model_calls"] == 0


def test_get_unknown_run_returns_error_envelope(client):
    """Unknown ids yield a 404 using the standard error envelope."""
    response = client.get("/api/runs/does-not-exist")

    assert response.status_code == 404, response.text
    body = response.json()
    assert "error" in body
    assert set(body["error"]) >= {"code", "message"}


# ---------------------------------------------------------------------------
# Contract-before-code: :start must fail until the contract is approved
# ---------------------------------------------------------------------------


def test_start_before_contract_approval_is_rejected(client, run_id):
    """Starting a run before contract approval MUST fail with 409."""
    response = client.post(f"/api/runs/{run_id}:start")

    assert response.status_code == 409, response.text
    body = response.json()
    assert "error" in body


def test_start_after_generate_but_before_approval_is_rejected(client, run_id):
    """Generating criteria is not approval; :start still fails with 409."""
    generated = client.post(
        f"/api/runs/{run_id}/criteria:generate", json={"mode": "hybrid"}
    )
    assert generated.status_code == 200, generated.text

    started = client.post(f"/api/runs/{run_id}:start")
    assert started.status_code == 409, started.text


# ---------------------------------------------------------------------------
# POST /api/runs/{id}/criteria:generate — hybrid generation grounded in files
# ---------------------------------------------------------------------------


def test_generate_hybrid_criteria_returns_contract(client, run_id):
    """Hybrid generation returns a contract of measurable, ordered criteria."""
    response = client.post(
        f"/api/runs/{run_id}/criteria:generate", json={"mode": "hybrid"}
    )

    assert response.status_code == 200, response.text
    contract = response.json()
    assert contract["run_id"] == run_id
    assert contract["mode"] == "hybrid"
    assert contract["approved"] is False
    assert isinstance(contract["criteria"], list) and contract["criteria"]

    # Each criterion is typed and prioritized (FR-001b/FR-001c).
    for criterion in contract["criteria"]:
        assert "id" in criterion
        assert criterion["type"] in {
            "command",
            "metric",
            "openapi",
            "git_policy",
            "database_assertion",
            "architecture",
        }
        assert "priority" in criterion


# ---------------------------------------------------------------------------
# PUT /api/runs/{id}/criteria — edit / prioritize before approval
# ---------------------------------------------------------------------------


def test_edit_criteria_before_approval(client, run_id):
    """The operator can edit at least one criterion prior to approval."""
    generated = client.post(
        f"/api/runs/{run_id}/criteria:generate", json={"mode": "hybrid"}
    )
    assert generated.status_code == 200, generated.text
    contract = generated.json()

    # Re-prioritize: reverse the priority ordering of the returned criteria.
    edited = contract["criteria"]
    for new_priority, criterion in enumerate(reversed(edited)):
        criterion["priority"] = new_priority

    response = client.put(f"/api/runs/{run_id}/criteria", json={"criteria": edited})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["approved"] is False
    assert len(body["criteria"]) == len(edited)


# ---------------------------------------------------------------------------
# POST /api/runs/{id}/criteria:approve — freeze the contract
# ---------------------------------------------------------------------------


def test_approve_freezes_contract_with_hash(client, run_id):
    """Approval freezes the contract and records a frozen hash (FR-003)."""
    generated = client.post(
        f"/api/runs/{run_id}/criteria:generate", json={"mode": "hybrid"}
    )
    assert generated.status_code == 200, generated.text

    response = client.post(f"/api/runs/{run_id}/criteria:approve")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["approved"] is True
    assert body.get("frozen_hash")


def test_edit_after_approval_is_rejected(client, approved_run_id):
    """A frozen contract cannot be edited (acceptance targets cannot move)."""
    response = client.put(
        f"/api/runs/{approved_run_id}/criteria", json={"criteria": []}
    )

    assert response.status_code == 409, response.text


# ---------------------------------------------------------------------------
# POST /api/runs/{id}:start — allowed once the contract is approved
# ---------------------------------------------------------------------------


def test_start_after_approval_is_accepted(client, approved_run_id):
    """Once the contract is frozen, :start is accepted (not a 409)."""
    response = client.post(f"/api/runs/{approved_run_id}:start")

    assert response.status_code in (200, 202), response.text
    body = response.json()
    # The run leaves the contract gate and begins executing.
    assert body["status"] in {"running", "awaiting_gate"}
