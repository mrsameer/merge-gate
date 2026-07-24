"""Unit tests for T026 — pure verdict computation over recorded state.

The acceptance engine (T025) runs commands and records CheckResults; this
module turns that recorded state into a Verdict + acceptance_hash without any
I/O. These tests use hand-crafted checks so T026 can land before the engine is
wired.
"""

from __future__ import annotations

import hashlib

import pytest

from mergegate.acceptance.verdict import (
    ACCEPTANCE_INPUT_KEYS,
    build_acceptance_input,
    compute_acceptance_hash,
    compute_verdict,
)
from mergegate.ledger.ledger import canonical_json
from mergegate.models import CheckResult, Verdict
from mergegate.models.enums import CheckStep


def _sample_input(**overrides) -> dict:
    base = {
        "commit_sha": "deadbeef",
        "validation_config": {"pipeline": ["build", "lint", "existing_tests"]},
        "tool_versions": {"pytest": "9.1.1", "ruff": "0.16.0"},
        "env_fingerprint": "py3.11-win32",
    }
    base.update(overrides)
    return base


def _check(*, passed: bool, step: CheckStep = CheckStep.EXISTING_TESTS) -> CheckResult:
    return CheckResult(
        criterion_id="task-tests",
        step=step,
        passed=passed,
        exit_code=0 if passed else 1,
        stdout="" if passed else "FAILED",
        stderr="",
        duration_ms=100,
    )


def test_build_acceptance_input_contains_required_fields() -> None:
    acceptance_input = build_acceptance_input(
        commit_sha="abc123",
        validation_config={"mode": "hybrid"},
        tool_versions={"pytest": "9.1.1"},
        env_fingerprint="py3.11-linux",
    )

    assert set(acceptance_input.keys()) == set(ACCEPTANCE_INPUT_KEYS)
    assert acceptance_input["commit_sha"] == "abc123"


def test_build_acceptance_input_rejects_blank_commit_sha() -> None:
    with pytest.raises(ValueError, match="commit_sha"):
        build_acceptance_input(
            commit_sha="",
            validation_config={},
            tool_versions={},
            env_fingerprint="py3.11-linux",
        )


def test_compute_acceptance_hash_is_deterministic() -> None:
    acceptance_input = _sample_input()

    first = compute_acceptance_hash(acceptance_input)
    second = compute_acceptance_hash(acceptance_input)

    expected = hashlib.sha256(
        canonical_json(acceptance_input).encode("utf-8")
    ).hexdigest()
    assert first == second == expected


def test_compute_acceptance_hash_changes_when_input_changes() -> None:
    base_hash = compute_acceptance_hash(_sample_input())
    changed_hash = compute_acceptance_hash(
        _sample_input(commit_sha="cafebabe")
    )

    assert base_hash != changed_hash


def test_all_checks_pass_yields_passed_verdict() -> None:
    checks = [
        _check(passed=True, step=CheckStep.BUILD),
        _check(passed=True, step=CheckStep.EXISTING_TESTS),
    ]
    acceptance_input = _sample_input()

    verdict = compute_verdict("attempt-1", checks, acceptance_input)

    assert isinstance(verdict, Verdict)
    assert verdict.attempt_id == "attempt-1"
    assert verdict.passed is True
    assert verdict.checks == checks
    assert verdict.acceptance_input == acceptance_input
    assert verdict.acceptance_hash == compute_acceptance_hash(acceptance_input)
    assert verdict.replay_of is None


def test_any_check_fails_yields_failed_verdict() -> None:
    checks = [
        _check(passed=True, step=CheckStep.BUILD),
        _check(passed=False, step=CheckStep.NEW_TESTS),
    ]

    verdict = compute_verdict("attempt-1", checks, _sample_input())

    assert verdict.passed is False
    assert verdict.acceptance_hash == compute_acceptance_hash(_sample_input())


def test_empty_checks_yields_failed_verdict() -> None:
    """No recorded evidence must not masquerade as success (Principle IV)."""

    verdict = compute_verdict("attempt-1", [], _sample_input())

    assert verdict.passed is False
    assert verdict.checks == []


def test_compute_verdict_is_pure() -> None:
    checks = [_check(passed=True)]
    acceptance_input = _sample_input()

    first = compute_verdict("attempt-1", checks, acceptance_input)
    second = compute_verdict("attempt-1", checks, acceptance_input)

    assert first == second


def test_replay_of_is_preserved() -> None:
    verdict = compute_verdict(
        "attempt-replay",
        [_check(passed=True)],
        _sample_input(),
        replay_of="attempt-original",
    )

    assert verdict.replay_of == "attempt-original"


def test_compute_verdict_rejects_incomplete_acceptance_input() -> None:
    with pytest.raises(ValueError, match="acceptance_input"):
        compute_verdict("attempt-1", [_check(passed=True)], {"commit_sha": "abc"})
