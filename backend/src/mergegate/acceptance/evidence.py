from __future__ import annotations

import hashlib

from mergegate.models import CheckResult, Criterion, RedGreenEvidence


def _output_hash(*, stdout: str, stderr: str, exit_code: int) -> str:
    payload = f"{exit_code}\n{stdout}\n{stderr}"
    return hashlib.sha256(payload.encode()).hexdigest()


def _test_hash(criterion: Criterion) -> str:
    content = criterion.command or criterion.id
    return hashlib.sha256(content.encode()).hexdigest()


def build_red_green_evidence(
    *,
    criterion: Criterion,
    baseline: CheckResult,
    result: CheckResult,
) -> RedGreenEvidence:
    baseline_failed = baseline.exit_code != 0
    result_passed = result.passed and result.exit_code == 0
    valid_proof = baseline_failed and result_passed
    return RedGreenEvidence(
        criterion_id=criterion.id,
        baseline="FAILED" if baseline_failed else "PASSED",
        result="PASSED" if result_passed else "FAILED",
        verdict="VALID PROOF" if valid_proof else "INVALID PROOF",
        test_hash=_test_hash(criterion),
        baseline_hash=_output_hash(
            stdout=baseline.stdout,
            stderr=baseline.stderr,
            exit_code=baseline.exit_code,
        ),
        result_hash=_output_hash(
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.exit_code,
        ),
        baseline_exit_code=baseline.exit_code,
        result_exit_code=result.exit_code,
        command=criterion.command or "",
    )
