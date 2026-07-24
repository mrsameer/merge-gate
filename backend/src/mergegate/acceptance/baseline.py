"""Baseline checks for the red-before/green-after proof (FR-009)."""

from __future__ import annotations

from mergegate.acceptance.engine import AcceptanceEngine
from mergegate.models import CheckResult, Contract, PassFail


def run_baseline_checks(
    contract: Contract, workspace: str, engine: AcceptanceEngine
) -> list[CheckResult]:
    """Run only task-specific red checks on the untouched baseline workspace.

    A baseline is valid only when at least one criterion explicitly marked
    ``baseline_expected=fail`` actually fails.  The caller records the captured
    command output regardless, so this validation cannot be faked by a model.
    """
    tracked = [
        criterion
        for criterion in contract.criteria
        if criterion.baseline_expected == PassFail.FAIL
    ]
    if not tracked:
        return []
    baseline_contract = contract.model_copy(update={"criteria": tracked})
    checks = engine.run(baseline_contract, workspace)
    if not any(not check.passed for check in checks):
        raise ValueError("baseline proof invalid: no relevant task test failed")
    return checks
