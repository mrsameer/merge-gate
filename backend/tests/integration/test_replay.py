"""US2 integration coverage for red→green proof and model-free replay."""

from __future__ import annotations

import time

import pytest


def _wait_for_gate(client, run_id: str, timeout_s: float = 45.0) -> dict:
    deadline = time.time() + timeout_s
    last: dict = {}
    while time.time() < deadline:
        response = client.get(f"/api/runs/{run_id}")
        assert response.status_code == 200, response.text
        last = response.json()
        if last["status"] == "awaiting_gate" and last["current_attempt"] >= 1:
            return last
        time.sleep(0.2)
    pytest.fail(f"run did not reach the final gate: {last!r}")


def test_run_records_genuine_red_green_proof_and_replays_without_model_calls(
    client, approved_run_id
):
    """The task test fails on the unmodified baseline, passes after the change,
    and replay rebuilds the same verdict without invoking a provider.
    """
    started = client.post(f"/api/runs/{approved_run_id}:start")
    assert started.status_code == 202, started.text
    _wait_for_gate(client, approved_run_id)

    attempts = client.get(f"/api/runs/{approved_run_id}/attempts")
    assert attempts.status_code == 200, attempts.text
    attempt = attempts.json()[-1]
    evidence = attempt["red_green_evidence"]
    assert evidence["baseline"] == "FAILED"
    assert evidence["result"] == "PASSED"
    assert evidence["verdict"] == "VALID_PROOF"
    assert len(evidence["test_hash"]) == 64
    assert len(evidence["baseline_hash"]) == 64
    assert len(evidence["result_hash"]) == 64

    before_replay = client.get(f"/api/runs/{approved_run_id}").json()
    replay = client.post(f"/api/runs/{approved_run_id}/replay")
    assert replay.status_code == 200, replay.text
    replayed = replay.json()
    assert replayed["replay_of"] == attempt["id"]
    assert replayed["acceptance_hash"] == attempt["verdict"]["acceptance_hash"]
    assert replayed["passed"] is attempt["verdict"]["passed"]

    after_replay = client.get(f"/api/runs/{approved_run_id}").json()
    assert after_replay["cost"]["model_calls"] == before_replay["cost"]["model_calls"]


def test_evidence_endpoint_returns_the_proof_rendered_by_the_operator_ui(
    client, approved_run_id
):
    assert client.post(f"/api/runs/{approved_run_id}:start").status_code == 202
    _wait_for_gate(client, approved_run_id)

    response = client.get(f"/api/runs/{approved_run_id}/evidence")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["red_green_evidence"]["verdict"] == "VALID_PROOF"
    assert body["verdict"]["acceptance_hash"]
