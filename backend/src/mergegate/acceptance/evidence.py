"""Deterministic red→green evidence records for completed attempts."""

from __future__ import annotations

import hashlib
import json

from pydantic import BaseModel

from mergegate.models import CheckResult, Contract, PassFail


class RedGreenEvidence(BaseModel):
    """Inspectable proof that a task check changed from red to green."""

    baseline: str
    result: str
    verdict: str
    test_hash: str
    baseline_hash: str
    result_hash: str


def _digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _check_payload(checks: list[CheckResult]) -> list[dict]:
    return [check.model_dump(mode="json") for check in checks]


def build_red_green_evidence(
    contract: Contract,
    baseline_checks: list[CheckResult],
    result_checks: list[CheckResult],
) -> RedGreenEvidence:
    """Build hashes and an honest proof verdict from captured check results."""
    tracked = [
        criterion
        for criterion in contract.criteria
        if criterion.baseline_expected == PassFail.FAIL
    ]
    ids = {criterion.id for criterion in tracked}
    baseline = [check for check in baseline_checks if check.criterion_id in ids]
    result = [check for check in result_checks if check.criterion_id in ids]
    baseline_failed = bool(baseline) and any(not check.passed for check in baseline)
    result_passed = bool(result) and all(check.passed for check in result)
    valid = baseline_failed and result_passed
    return RedGreenEvidence(
        baseline="FAILED" if baseline_failed else "PASSED",
        result="PASSED" if result_passed else "FAILED",
        verdict="VALID_PROOF" if valid else "INVALID",
        test_hash=_digest(
            [
                {
                    "id": criterion.id,
                    "command": criterion.command,
                    "baseline_expected": criterion.baseline_expected,
                    "result_expected": criterion.result_expected,
                }
                for criterion in tracked
            ]
        ),
        baseline_hash=_digest(_check_payload(baseline)),
        result_hash=_digest(_check_payload(result)),
    )
