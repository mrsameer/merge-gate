"""Integration test: objective → contract → run → SUCCESS (T021)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mergegate.api.runs import create_app
from mergegate.config.settings import Settings

OBJECTIVE = (
    "Add idempotent order creation to POST /orders. Require an Idempotency-Key header. "
    "Do not modify the auth module."
)


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    repo_root = Path(__file__).resolve().parents[3]
    os.environ["MERGEGATE_DATA_DIR"] = str(tmp_path / "data")
    os.environ["MERGEGATE_DEMO_REPO_PATH"] = str(repo_root / "demo-repo")
    import mergegate.config.settings as settings_module

    settings_module.get_settings = lambda: Settings(
        data_dir=tmp_path / "data",
        demo_repo_path=repo_root / "demo-repo",
        harness_provider="stub",
        default_workflow_id="default-four-role-loop",
    )
    return TestClient(create_app())


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
