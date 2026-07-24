from __future__ import annotations

from pathlib import Path

from mergegate.acceptance.commands import run_command
from mergegate.models import CheckResult, CheckStep, Contract, Criterion, ExpectedResult


class BaselineNotRedError(RuntimeError):
    """Raised when a task test passes on the baseline when it must fail."""


def run_baseline_check(criterion: Criterion, *, workspace: Path) -> CheckResult:
    """Run a criterion on the baseline worktree; expect failure for red-before proof."""
    command = criterion.command or "false"
    result = run_command(command, cwd=str(workspace))
    failed_as_expected = result.exit_code != 0
    if criterion.baseline_expected == ExpectedResult.FAIL and not failed_as_expected:
        raise BaselineNotRedError(
            f"criterion {criterion.id} passed on baseline but must fail first"
        )
    return CheckResult(
        criterion_id=criterion.id,
        step=CheckStep.NEW_TESTS,
        passed=failed_as_expected,
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        duration_ms=result.duration_ms,
        baseline_result=ExpectedResult.FAIL
        if failed_as_expected
        else ExpectedResult.PASS,
    )


def run_baseline_checks(contract: Contract, *, workspace: Path) -> list[CheckResult]:
    """Run all criteria that require a genuine baseline failure."""
    results: list[CheckResult] = []
    for criterion in sorted(contract.criteria, key=lambda c: c.priority):
        if criterion.baseline_expected == ExpectedResult.FAIL:
            results.append(run_baseline_check(criterion, workspace=workspace))
    return results
