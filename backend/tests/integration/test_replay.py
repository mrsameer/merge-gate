"""Integration test: red-before/green-after + replay with zero model calls (T031)."""

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


def test_red_before_green_after_and_replay_zero_model_calls(
    client: TestClient,
) -> None:
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
    attempt = body["attempts"][0]
    evidence = attempt.get("evidence")
    assert evidence is not None
    assert evidence["baseline"] == "FAILED"
    assert evidence["result"] == "PASSED"
    assert evidence["verdict"] == "VALID PROOF"
    assert evidence["test_hash"]
    assert evidence["baseline_hash"]
    assert evidence["result_hash"]

    original_hash = attempt["verdict"]["acceptance_hash"]
    model_calls_before = body["cost"]["model_calls"]

    replay = client.post(f"/api/runs/{run_id}/replay")
    assert replay.status_code == 200
    replay_body = replay.json()
    assert replay_body["acceptance_hash"] == original_hash
    assert replay_body["replay_of"] == original_hash

    run_after = client.get(f"/api/runs/{run_id}")
    assert run_after.json()["cost"]["model_calls"] == model_calls_before
