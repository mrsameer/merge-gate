"""T068 saved demo workflows stay portable, deterministic, and runnable."""

from __future__ import annotations

from pathlib import Path

import pytest

from mergegate.models import AgentRole, NodeType, RunStatus
from mergegate.orchestrator.default_workflow import build_default_workflow
from mergegate.orchestrator.serialize import (
    deserialize_workflow,
    serialize_workflow,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES_DIR = REPO_ROOT / "demo-repo" / "fixtures"
DEFAULT_WORKFLOW_FIXTURE = FIXTURES_DIR / "default-four-role-workflow.yaml"
CONTRADICTORY_TASK_FIXTURE = FIXTURES_DIR / "contradictory-task-workflow.yaml"
CONTRADICTORY_OBJECTIVE = (
    "POST /orders must return both 200 and 201 for the same successful request."
)


def _load_fixture(path: Path):
    content = path.read_text(encoding="utf-8")
    return content, deserialize_workflow(content, "yaml")


def test_default_four_role_fixture_matches_the_canonical_workflow() -> None:
    content, workflow = _load_fixture(DEFAULT_WORKFLOW_FIXTURE)

    assert workflow == build_default_workflow("default-four-role-loop")
    assert serialize_workflow(workflow, "yaml") == content
    assert [
        node.config.role
        for node in workflow.nodes
        if node.config is not None and node.config.role is not None
    ] == [
        AgentRole.SUCCESS_CRITERIA,
        AgentRole.PLANNING,
        AgentRole.EXECUTION,
        AgentRole.VALIDATION,
    ]


def test_contradictory_task_fixture_is_canonical_and_carries_saved_objective() -> None:
    content, workflow = _load_fixture(CONTRADICTORY_TASK_FIXTURE)

    assert serialize_workflow(workflow, "yaml") == content
    input_node = next(node for node in workflow.nodes if node.type == NodeType.INPUT)
    assert input_node.config is not None
    assert input_node.config.instructions == CONTRADICTORY_OBJECTIVE


@pytest.mark.parametrize(
    "fixture_path",
    [DEFAULT_WORKFLOW_FIXTURE, CONTRADICTORY_TASK_FIXTURE],
)
def test_saved_workflow_fixture_round_trips_through_public_api(
    client, fixture_path: Path
) -> None:
    content, workflow = _load_fixture(fixture_path)

    imported = client.post(
        "/api/workflows/import",
        json={"format": "yaml", "content": content},
    )
    assert imported.status_code == 201, imported.text
    assert imported.json() == workflow.model_dump(mode="json")

    exported = client.post(f"/api/workflows/{workflow.id}/export?format=yaml")
    assert exported.status_code == 200, exported.text
    assert exported.text == content

    reimported = client.post(
        "/api/workflows/import",
        json={"format": "yaml", "content": exported.text},
    )
    assert reimported.status_code == 201, reimported.text
    assert reimported.json() == imported.json()


def test_contradictory_task_fixture_halts_without_execution(client, demo_repo) -> None:
    content, workflow = _load_fixture(CONTRADICTORY_TASK_FIXTURE)
    imported = client.post(
        "/api/workflows/import",
        json={"format": "yaml", "content": content},
    )
    assert imported.status_code == 201, imported.text

    input_node = next(node for node in workflow.nodes if node.type == NodeType.INPUT)
    assert input_node.config is not None
    assert input_node.config.instructions is not None

    created = client.post(
        "/api/runs",
        json={
            "workflow_id": workflow.id,
            "objective": input_node.config.instructions,
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
        f"/api/runs/{run_id}/criteria:generate",
        json={"mode": "hybrid"},
    )
    assert generated.status_code == 200, generated.text
    approved = client.post(f"/api/runs/{run_id}/criteria:approve")
    assert approved.status_code == 200, approved.text

    started = client.post(f"/api/runs/{run_id}:start")

    assert started.status_code == 200, started.text
    assert started.json()["status"] == RunStatus.CLARIFICATION_REQUIRED.value
    assert started.json()["current_attempt"] == 0
    assert started.json()["attempts"] == []
    assert started.json()["cost"]["model_calls"] == 0
    assert started.json()["clarification"]["conflicting_criteria"] == ["feature-exists"]
