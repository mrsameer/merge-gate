"""Contract tests for US1 runs API (T020)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mergegate.api.runs import create_app
from mergegate.config.settings import Settings


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


def test_start_before_contract_approval_returns_409(client: TestClient) -> None:
    create = client.post(
        "/api/runs",
        json={
            "workflow_id": "default-four-role-loop",
            "objective": "Add idempotent orders",
            "repo_ref": "demo-repo",
        },
    )
    assert create.status_code == 201
    run_id = create.json()["id"]
    start = client.post(f"/api/runs/{run_id}:start")
    assert start.status_code == 409


def test_criteria_generate_approve_and_get_run(client: TestClient) -> None:
    create = client.post(
        "/api/runs",
        json={
            "workflow_id": "default-four-role-loop",
            "objective": "Add idempotent order creation to POST /orders",
            "repo_ref": "demo-repo",
        },
    )
    run_id = create.json()["id"]
    generated = client.post(f"/api/runs/{run_id}/criteria:generate")
    assert generated.status_code == 200
    contract = generated.json()["contract"]
    assert contract["approved"] is False
    assert len(contract["criteria"]) >= 1

    approved = client.post(f"/api/runs/{run_id}/criteria:approve")
    assert approved.status_code == 200
    assert approved.json()["contract"]["approved"] is True
    assert approved.json()["contract"]["frozen_hash"]

    run = client.get(f"/api/runs/{run_id}")
    assert run.status_code == 200
    assert run.json()["contract"]["approved"] is True
