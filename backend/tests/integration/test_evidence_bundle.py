"""T052/T055 — completed runs export complete, tamper-evident receipts."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from mergegate.ledger.verify import verify_chain


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


def _complete_run(client, run_id: str) -> None:
    started = client.post(f"/api/runs/{run_id}:start")
    assert started.status_code == 202, started.text
    _wait_for_gate(client, run_id)
    approved = client.post(f"/api/runs/{run_id}/gate:approve", json={"kind": "final"})
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "SUCCESS"


def test_completed_run_exports_schema_valid_bundle_with_intact_chain(
    client, approved_run_id
) -> None:
    _complete_run(client, approved_run_id)

    ledger_response = client.get(f"/api/runs/{approved_run_id}/ledger")
    assert ledger_response.status_code == 200, ledger_response.text
    ledger = ledger_response.json()
    assert [entry["seq"] for entry in ledger] == list(range(1, len(ledger) + 1))
    assert verify_chain(ledger).valid is True
    assert {
        "objective",
        "contract",
        "plan",
        "harness",
        "policy",
        "command",
        "verdict",
        "gate",
        "terminal",
    } <= {entry["type"] for entry in ledger}

    response = client.get(f"/api/runs/{approved_run_id}/evidence")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/json")
    assert (
        response.headers["content-disposition"]
        == 'attachment; filename="evidence-bundle.json"'
    )
    bundle = response.json()

    schema_path = (
        Path(__file__).resolve().parents[3]
        / "specs"
        / "001-mergegate-control-plane"
        / "contracts"
        / "evidence-bundle.schema.json"
    )
    with schema_path.open(encoding="utf-8") as schema_file:
        Draft202012Validator(json.load(schema_file)).validate(bundle)

    assert bundle["run_id"] == approved_run_id
    assert bundle["terminal_state"] == "SUCCESS"
    assert bundle["contract"]["frozen_hash"]
    assert bundle["plan"]
    assert bundle["diff"]
    assert bundle["commands"]
    assert all("exit_code" in command for command in bundle["commands"])
    assert bundle["red_green_evidence"]["verdict"] == "VALID_PROOF"
    assert bundle["policy_results"]
    assert all(result["passed"] is True for result in bundle["policy_results"])
    assert {result["rule"] for result in bundle["policy_results"]} == {
        "app/auth/**",
        "tests/acceptance/**",
        "pytest.mark.skip",
        "eslint-disable",
        "assert True",
    }
    assert isinstance(bundle["retries"], list)
    assert len(bundle["acceptance_hash"]) == 64
    assert bundle["cost"]["model_calls"] >= 0
    assert bundle["time"]["ended_at"]
    assert verify_chain(bundle["ledger"]).valid is True


def test_altering_a_prior_bundle_entry_is_reported_as_tampering(
    client, approved_run_id
) -> None:
    _complete_run(client, approved_run_id)
    bundle = client.get(f"/api/runs/{approved_run_id}/evidence").json()

    bundle["ledger"][0]["payload"]["objective"] = "silently changed"
    result = verify_chain(bundle["ledger"])

    assert result.valid is False
    assert result.broken_seq == 1
    assert result.reason is not None
    assert "hash" in result.reason


def test_incomplete_run_keeps_the_existing_validator_proof_response(
    client, approved_run_id
) -> None:
    started = client.post(f"/api/runs/{approved_run_id}:start")
    assert started.status_code == 202
    _wait_for_gate(client, approved_run_id)

    response = client.get(f"/api/runs/{approved_run_id}/evidence")
    assert response.status_code == 200, response.text
    assert "content-disposition" not in response.headers
    assert response.json()["red_green_evidence"]["verdict"] == "VALID_PROOF"
