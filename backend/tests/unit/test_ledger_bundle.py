"""T053 — evidence bundles are assembled from and checked against the contract."""

from datetime import UTC, datetime, timedelta

import pytest
from jsonschema import ValidationError

from mergegate.ledger.bundle import assemble_evidence_bundle, validate_bundle
from mergegate.ledger.ledger import LedgerWriter
from mergegate.ledger.store import connect
from mergegate.models import (
    Budget,
    Contract,
    ContractMode,
    CostAccounting,
    Criterion,
    CriterionType,
    Run,
    RunStatus,
)
from mergegate.models.enums import LedgerEntryType


def _completed_run() -> Run:
    started = datetime.now(UTC) - timedelta(seconds=4)
    return Run(
        id="r1",
        workflow_id="wf-1",
        objective="ship receipts",
        repo_ref="repo",
        status=RunStatus.SUCCESS,
        budgets=Budget(max_attempts=2, max_wall_clock_s=60, max_model_calls=2),
        current_attempt=1,
        cost=CostAccounting(tokens=42, model_calls=1, usd=0.01, wall_clock_s=3.5),
        started_at=started,
        ended_at=started + timedelta(seconds=4),
    )


def _contract() -> Contract:
    return Contract(
        id="contract-r1",
        run_id="r1",
        mode=ContractMode.HYBRID,
        criteria=[Criterion(id="tests", type=CriterionType.COMMAND, priority=1)],
        approved=True,
        frozen_hash="frozen-contract",
    )


def _entries(tmp_path):
    conn = connect(":memory:")
    conn.execute(
        "INSERT INTO runs (id, workflow_id, objective, repo_ref, status, "
        "budgets, current_attempt, cost) VALUES "
        "('r1', 'wf-1', 'objective', 'repo', 'SUCCESS', '{}', 1, '{}')"
    )
    conn.commit()
    writer = LedgerWriter(conn, "r1", tmp_path / "r1.jsonl")
    writer.append(LedgerEntryType.PLAN, {"plan": "make the proof inspectable"})
    writer.append(
        LedgerEntryType.HARNESS,
        {
            "attempt": 1,
            "diff": "+proof",
            "changed_files": ["proof.py"],
            "tokens": 42,
            "model_calls": 1,
            "usd": 0.01,
            "wall_clock_s": 3.5,
        },
    )
    writer.append(
        LedgerEntryType.COMMAND,
        {
            "command": "pytest -q",
            "exit_code": 0,
            "stdout": "1 passed",
            "stderr": "",
            "duration_ms": 12,
        },
    )
    writer.append(
        LedgerEntryType.VERDICT,
        {
            "acceptance_hash": "acceptance-hash",
            "acceptance_input": {
                "commit_sha": "abc",
                "validation_config": {},
                "tool_versions": {"python": "3.11"},
                "env_fingerprint": "test",
            },
            "red_green_evidence": {
                "baseline": "FAILED",
                "result": "PASSED",
                "verdict": "VALID_PROOF",
                "test_hash": "test",
                "baseline_hash": "red",
                "result_hash": "green",
            },
        },
    )
    writer.append(
        LedgerEntryType.POLICY,
        {
            "attempt": 1,
            "kind": "protected_path",
            "rule": "app/auth/**",
            "passed": True,
        },
    )
    writer.append(LedgerEntryType.GATE, {"gate": "merge", "decision": "approve"})
    writer.append(LedgerEntryType.TERMINAL, {"status": "SUCCESS"})
    return writer.read_entries()


def test_assembler_emits_every_required_receipt_field(tmp_path) -> None:
    bundle = assemble_evidence_bundle(
        run=_completed_run(),
        contract=_contract(),
        entries=_entries(tmp_path),
    )

    validate_bundle(bundle)
    assert bundle["run_id"] == "r1"
    assert bundle["terminal_state"] == "SUCCESS"
    assert bundle["contract"]["frozen_hash"] == "frozen-contract"
    assert bundle["plan"] == "make the proof inspectable"
    assert bundle["diff"] == "+proof"
    assert bundle["commands"][0]["exit_code"] == 0
    assert bundle["red_green_evidence"]["verdict"] == "VALID_PROOF"
    assert bundle["policy_results"] == [
        {
            "attempt": 1,
            "kind": "protected_path",
            "rule": "app/auth/**",
            "passed": True,
        }
    ]
    assert bundle["retries"] == []
    assert bundle["acceptance_hash"] == "acceptance-hash"
    assert bundle["cost"]["model_calls"] == 1
    assert bundle["time"]["wall_clock_s"] == 4.0
    assert len(bundle["ledger"]) == 7


def test_bundle_validation_rejects_missing_required_evidence(tmp_path) -> None:
    bundle = assemble_evidence_bundle(
        run=_completed_run(),
        contract=_contract(),
        entries=_entries(tmp_path),
    )
    del bundle["acceptance_hash"]

    with pytest.raises(ValidationError):
        validate_bundle(bundle)
