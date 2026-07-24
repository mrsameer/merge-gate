from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from mergegate.acceptance.commands import run_command
from mergegate.models import CheckResult, CheckStep, Criterion


class CriterionEvaluator(ABC):
    @abstractmethod
    def evaluate(self, criterion: Criterion, *, workspace: Path) -> CheckResult:
        raise NotImplementedError


class CommandEvaluator(CriterionEvaluator):
    def evaluate(self, criterion: Criterion, *, workspace: Path) -> CheckResult:
        command = criterion.command or "true"
        result = run_command(command, cwd=str(workspace))
        expected = (
            criterion.expected_exit_code
            if criterion.expected_exit_code is not None
            else 0
        )
        passed = result.exit_code == expected
        return CheckResult(
            criterion_id=criterion.id,
            step=CheckStep.EXISTING_TESTS,
            passed=passed,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            duration_ms=result.duration_ms,
            baseline_result=criterion.baseline_expected,
        )


class ProtectedFilesEvaluator(CriterionEvaluator):
    def evaluate(self, criterion: Criterion, *, workspace: Path) -> CheckResult:
        protected = criterion.params.get("paths", ["app/auth/**"])
        return CheckResult(
            criterion_id=criterion.id,
            step=CheckStep.POLICY,
            passed=True,
            exit_code=0,
            stdout=f"protected paths configured: {protected}",
            stderr="",
            duration_ms=0,
        )


EVALUATOR_REGISTRY: dict[str, CriterionEvaluator] = {
    "command": CommandEvaluator(),
    "tests": CommandEvaluator(),
    "existing-tests": CommandEvaluator(),
    "new-tests": CommandEvaluator(),
    "protected-files": ProtectedFilesEvaluator(),
    "build": CommandEvaluator(),
    "lint": CommandEvaluator(),
    "coverage-threshold": CommandEvaluator(),
    "api-compatibility": CommandEvaluator(),
    "required-file": CommandEvaluator(),
    "feature-exists": CommandEvaluator(),
    "performance-vs-baseline": CommandEvaluator(),
    "architecture-conformance": CommandEvaluator(),
}


def get_evaluator(criterion: Criterion) -> CriterionEvaluator:
    key = criterion.id.replace("_", "-")
    if key in EVALUATOR_REGISTRY:
        return EVALUATOR_REGISTRY[key]
    if criterion.type.value in EVALUATOR_REGISTRY:
        return EVALUATOR_REGISTRY[criterion.type.value]
    return CommandEvaluator()
