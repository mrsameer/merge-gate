"""Criterion-evaluator registry — the pluggable unit the engine (T025) drives.

An *evaluator* turns one `Criterion` into a `CheckResult` by running the
criterion's command (or a step-specific default command when none is given)
through the deterministic `run_command` primitive (T024). The engine (T025)
owns pipeline *ordering*; this module owns *how a single step is evaluated*,
so new criterion shapes can be added without touching the pipeline loop
(FR-001c's per-type coverage lands in T073 by registering more evaluators
here — this module is designed to be extended, not reworked).

Every evaluator has the signature::

    Evaluator(criterion: Criterion, *, workspace: str) -> CheckResult

and is looked up from `EVALUATOR_REGISTRY` by `criterion.step`. A criterion
with no registered evaluator for its step, or no `step` set at all, is the
engine's concern (it is skipped from the ordered pipeline) — this module only
evaluates criteria it is asked to evaluate.
"""

from __future__ import annotations

from collections.abc import Callable

from mergegate.acceptance.commands import run_command
from mergegate.models.contract import Criterion
from mergegate.models.enums import CheckStep, PassFail
from mergegate.models.verdict import CheckResult

Evaluator = Callable[[Criterion, str], CheckResult]

# Default commands per step, used only when a criterion does not supply its
# own `command`. Callers targeting a real project (e.g. demo-repo, a `uv`
# project) get sane defaults for free; anything more specific (a particular
# lint rule set, a particular coverage threshold check) is expressed on the
# criterion itself.
_DEFAULT_COMMANDS: dict[CheckStep, str] = {
    CheckStep.BUILD: "uv run python -m compileall -q app",
    CheckStep.LINT: "uv run ruff check .",
    CheckStep.EXISTING_TESTS: "uv run pytest tests -q",
    CheckStep.NEW_TESTS: "uv run pytest tests -q",
    CheckStep.MIGRATION: "uv run python -c \"pass\"",
    CheckStep.API_CONTRACT: "uv run pytest tests -q -k openapi",
}


def _command_for(criterion: Criterion, step: CheckStep) -> str:
    """Resolve the command to run: the criterion's own, else the step default."""
    if criterion.command:
        return criterion.command
    default = _DEFAULT_COMMANDS.get(step)
    if default is None:
        raise ValueError(
            f"criterion {criterion.id!r} for step {step!r} has no command and "
            "no step default is registered"
        )
    return default


def _run_command_criterion(
    criterion: Criterion, workspace: str, step: CheckStep
) -> CheckResult:
    """Shared implementation for every command-shaped step evaluator.

    Pass/fail is exit-code-based: `expected_exit_code` if the criterion sets
    one, else zero. This keeps the decision a pure function of recorded
    command state (Principle II) — no output-string sniffing.
    """
    command = _command_for(criterion, step)
    result = run_command(command, cwd=workspace)
    expected_exit_code = (
        criterion.expected_exit_code if criterion.expected_exit_code is not None else 0
    )
    passed = (not result.timed_out) and result.exit_code == expected_exit_code
    return CheckResult(
        criterion_id=criterion.id,
        step=step,
        passed=passed,
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        duration_ms=result.duration_ms,
    )


def evaluate_build(criterion: Criterion, workspace: str) -> CheckResult:
    """The project must build (compile) successfully (FR-001c)."""
    return _run_command_criterion(criterion, workspace, CheckStep.BUILD)


def evaluate_lint(criterion: Criterion, workspace: str) -> CheckResult:
    """Static analysis / lint must pass."""
    return _run_command_criterion(criterion, workspace, CheckStep.LINT)


def evaluate_existing_tests(criterion: Criterion, workspace: str) -> CheckResult:
    """Existing tests must continue to pass (FR-001c)."""
    return _run_command_criterion(criterion, workspace, CheckStep.EXISTING_TESTS)


def evaluate_new_tests(criterion: Criterion, workspace: str) -> CheckResult:
    """New, task-specific tests must exist and pass (FR-001c).

    This is also the red-before/green-after step (FR-009): the same
    `criterion.command` is run once against the baseline worktree
    (`baseline_expected=FAIL`) and once against the changed worktree
    (`result_expected=PASS`) by the engine/baseline module (T032); this
    evaluator just executes the command and records the outcome for whichever
    worktree it is pointed at via `workspace`.
    """
    result = _run_command_criterion(criterion, workspace, CheckStep.NEW_TESTS)
    tracks_baseline = (
        criterion.baseline_expected is not None or criterion.result_expected is not None
    )
    if tracks_baseline:
        observed = PassFail.PASS if result.passed else PassFail.FAIL
        return CheckResult(
            criterion_id=result.criterion_id,
            step=result.step,
            passed=result.passed,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            duration_ms=result.duration_ms,
            baseline_result=observed,
        )
    return result


def evaluate_migration(criterion: Criterion, workspace: str) -> CheckResult:
    """Migrations must apply and roll back cleanly.

    `criterion.params["rollback_command"]` (when set) is run immediately after
    the apply command; the step only passes if apply succeeds AND (when a
    rollback command is given) rollback also succeeds, so a migration that
    can't be undone cannot pass this check.
    """
    apply_result = _run_command_criterion(criterion, workspace, CheckStep.MIGRATION)
    rollback_command = (criterion.params or {}).get("rollback_command")
    if rollback_command is None:
        return apply_result

    rollback = run_command(rollback_command, cwd=workspace)
    passed = apply_result.passed and not rollback.timed_out and rollback.exit_code == 0
    combined_stdout = apply_result.stdout + "\n--- rollback ---\n" + rollback.stdout
    combined_stderr = apply_result.stderr + "\n--- rollback ---\n" + rollback.stderr
    return CheckResult(
        criterion_id=criterion.id,
        step=CheckStep.MIGRATION,
        passed=passed,
        exit_code=rollback.exit_code if apply_result.passed else apply_result.exit_code,
        stdout=combined_stdout,
        stderr=combined_stderr,
        duration_ms=apply_result.duration_ms + rollback.duration_ms,
    )


def evaluate_coverage(criterion: Criterion, workspace: str) -> CheckResult:
    """Coverage must reach `criterion.minimum` (FR-001c).

    Runs `criterion.command` (expected to emit a bare numeric percentage on
    stdout, e.g. `coverage report | tail -1 | ...`), and passes only if the
    parsed number is >= `minimum`. A minimum of `None` degrades to a plain
    command-succeeded check.
    """
    command = _command_for(criterion, CheckStep.COVERAGE)
    result = run_command(command, cwd=workspace)

    if result.timed_out or result.exit_code != 0:
        return CheckResult(
            criterion_id=criterion.id,
            step=CheckStep.COVERAGE,
            passed=False,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            duration_ms=result.duration_ms,
        )

    passed = True
    if criterion.minimum is not None:
        observed = _parse_trailing_percentage(result.stdout)
        passed = observed is not None and observed >= criterion.minimum

    return CheckResult(
        criterion_id=criterion.id,
        step=CheckStep.COVERAGE,
        passed=passed,
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        duration_ms=result.duration_ms,
    )


def _parse_trailing_percentage(stdout: str) -> float | None:
    """Extract a trailing `NN` or `NN.N` percentage from the last non-blank line."""
    lines = [line for line in stdout.splitlines() if line.strip()]
    if not lines:
        return None
    last = lines[-1].strip().rstrip("%")
    token = last.split()[-1] if last.split() else last
    try:
        return float(token)
    except ValueError:
        return None


def evaluate_api_contract(criterion: Criterion, workspace: str) -> CheckResult:
    """Public API / OpenAPI compatibility must hold (FR-001c)."""
    return _run_command_criterion(criterion, workspace, CheckStep.API_CONTRACT)


EVALUATOR_REGISTRY: dict[CheckStep, Evaluator] = {
    CheckStep.BUILD: evaluate_build,
    CheckStep.LINT: evaluate_lint,
    CheckStep.EXISTING_TESTS: evaluate_existing_tests,
    CheckStep.NEW_TESTS: evaluate_new_tests,
    CheckStep.MIGRATION: evaluate_migration,
    CheckStep.COVERAGE: evaluate_coverage,
    CheckStep.API_CONTRACT: evaluate_api_contract,
}
"""Maps each ordered pipeline step to its evaluator. `CheckStep.POLICY` is
intentionally absent — anti-cheat policy is enforced by `acceptance/policy.py`
(US5), not by a criterion evaluator, per plan.md's module split."""


def register_evaluator(step: CheckStep, evaluator: Evaluator) -> None:
    """Register or override the evaluator for `step`.

    Exists so T073 (full FR-001c type coverage) and later stories can extend
    or swap evaluators without editing this module or the engine.
    """
    EVALUATOR_REGISTRY[step] = evaluator
