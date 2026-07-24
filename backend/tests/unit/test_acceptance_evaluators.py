"""Unit tests for the criterion-evaluator registry (supports T025).

Each evaluator is exercised against a real, throwaway project in `tmp_path` so
the assertions are about actual command execution and exit-code-based
pass/fail — never about mocked behavior — matching Principle II (deterministic
acceptance is a function of real recorded state).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from mergegate.acceptance.evaluators import (
    EVALUATOR_REGISTRY,
    evaluate_api_contract,
    evaluate_architecture,
    evaluate_build,
    evaluate_coverage,
    evaluate_existing_tests,
    evaluate_lint,
    evaluate_migration,
    evaluate_new_tests,
    evaluate_performance,
    evaluate_protected_files,
    evaluate_required_file,
    register_evaluator,
)
from mergegate.models.contract import Criterion
from mergegate.models.enums import CheckStep, CriterionType, PassFail


def _py_command(code: str) -> str:
    return f'"{sys.executable}" -c "{code}"'


def test_build_evaluator_passes_on_zero_exit(tmp_path: Path) -> None:
    criterion = Criterion(
        id="build",
        type=CriterionType.COMMAND,
        priority=1,
        step=CheckStep.BUILD,
        command=_py_command("import sys; sys.exit(0)"),
    )
    result = evaluate_build(criterion, str(tmp_path))

    assert result.passed is True
    assert result.step == CheckStep.BUILD
    assert result.criterion_id == "build"
    assert result.exit_code == 0


def test_build_evaluator_fails_on_nonzero_exit(tmp_path: Path) -> None:
    criterion = Criterion(
        id="build",
        type=CriterionType.COMMAND,
        priority=1,
        step=CheckStep.BUILD,
        command=_py_command("import sys; sys.exit(1)"),
    )
    result = evaluate_build(criterion, str(tmp_path))

    assert result.passed is False
    assert result.exit_code == 1


def test_lint_evaluator_honors_expected_exit_code(tmp_path: Path) -> None:
    """A criterion may expect a non-zero exit code as its "pass" condition."""
    criterion = Criterion(
        id="lint-expect-2",
        type=CriterionType.COMMAND,
        priority=1,
        step=CheckStep.LINT,
        command=_py_command("import sys; sys.exit(2)"),
        expected_exit_code=2,
    )
    result = evaluate_lint(criterion, str(tmp_path))

    assert result.passed is True
    assert result.exit_code == 2


def test_existing_tests_evaluator_runs_given_command(tmp_path: Path) -> None:
    criterion = Criterion(
        id="existing-tests",
        type=CriterionType.COMMAND,
        priority=1,
        step=CheckStep.EXISTING_TESTS,
        command=_py_command("print('5 passed'); import sys; sys.exit(0)"),
    )
    result = evaluate_existing_tests(criterion, str(tmp_path))

    assert result.passed is True
    assert "5 passed" in result.stdout


def test_new_tests_evaluator_records_baseline_result_when_expected(
    tmp_path: Path,
) -> None:
    """Red-before/green-after (FR-009): baseline_result mirrors the outcome."""
    failing = Criterion(
        id="task-tests",
        type=CriterionType.COMMAND,
        priority=1,
        step=CheckStep.NEW_TESTS,
        command=_py_command("import sys; sys.exit(1)"),
        baseline_expected=PassFail.FAIL,
    )
    result = evaluate_new_tests(failing, str(tmp_path))

    assert result.passed is False
    assert result.baseline_result == PassFail.FAIL

    passing = Criterion(
        id="task-tests",
        type=CriterionType.COMMAND,
        priority=1,
        step=CheckStep.NEW_TESTS,
        command=_py_command("import sys; sys.exit(0)"),
        result_expected=PassFail.PASS,
    )
    green = evaluate_new_tests(passing, str(tmp_path))
    assert green.passed is True
    # result_expected alone (no baseline_expected) still records the observed
    # outcome as a baseline_result, since either flag signals "track this".
    assert green.baseline_result == PassFail.PASS


def test_new_tests_evaluator_omits_baseline_result_when_not_tracked(
    tmp_path: Path,
) -> None:
    criterion = Criterion(
        id="plain",
        type=CriterionType.COMMAND,
        priority=1,
        step=CheckStep.NEW_TESTS,
        command=_py_command("import sys; sys.exit(0)"),
    )
    result = evaluate_new_tests(criterion, str(tmp_path))
    assert result.baseline_result is None


def test_migration_evaluator_passes_when_apply_and_rollback_both_succeed(
    tmp_path: Path,
) -> None:
    criterion = Criterion(
        id="migration",
        type=CriterionType.COMMAND,
        priority=1,
        step=CheckStep.MIGRATION,
        command=_py_command("print('applied'); import sys; sys.exit(0)"),
        params={"rollback_command": _py_command("print('rolled back')")},
    )
    result = evaluate_migration(criterion, str(tmp_path))

    assert result.passed is True
    assert "applied" in result.stdout
    assert "rolled back" in result.stdout


def test_migration_evaluator_fails_when_rollback_fails(tmp_path: Path) -> None:
    criterion = Criterion(
        id="migration",
        type=CriterionType.COMMAND,
        priority=1,
        step=CheckStep.MIGRATION,
        command=_py_command("import sys; sys.exit(0)"),
        params={"rollback_command": _py_command("import sys; sys.exit(1)")},
    )
    result = evaluate_migration(criterion, str(tmp_path))

    assert result.passed is False


def test_migration_evaluator_without_rollback_command_only_checks_apply(
    tmp_path: Path,
) -> None:
    criterion = Criterion(
        id="migration",
        type=CriterionType.COMMAND,
        priority=1,
        step=CheckStep.MIGRATION,
        command=_py_command("import sys; sys.exit(0)"),
    )
    result = evaluate_migration(criterion, str(tmp_path))
    assert result.passed is True


def test_coverage_evaluator_passes_when_at_or_above_minimum(tmp_path: Path) -> None:
    criterion = Criterion(
        id="coverage",
        type=CriterionType.METRIC,
        priority=1,
        step=CheckStep.COVERAGE,
        command=_py_command("print('TOTAL 87')"),
        minimum=80.0,
    )
    result = evaluate_coverage(criterion, str(tmp_path))

    assert result.passed is True
    assert result.step == CheckStep.COVERAGE


def test_coverage_evaluator_fails_when_below_minimum(tmp_path: Path) -> None:
    criterion = Criterion(
        id="coverage",
        type=CriterionType.METRIC,
        priority=1,
        step=CheckStep.COVERAGE,
        command=_py_command("print('TOTAL 42')"),
        minimum=80.0,
    )
    result = evaluate_coverage(criterion, str(tmp_path))

    assert result.passed is False


def test_coverage_evaluator_fails_on_unparseable_output(tmp_path: Path) -> None:
    criterion = Criterion(
        id="coverage",
        type=CriterionType.METRIC,
        priority=1,
        step=CheckStep.COVERAGE,
        command=_py_command("print('no numbers here')"),
        minimum=80.0,
    )
    result = evaluate_coverage(criterion, str(tmp_path))

    assert result.passed is False


def test_coverage_evaluator_without_minimum_is_a_plain_success_check(
    tmp_path: Path,
) -> None:
    criterion = Criterion(
        id="coverage",
        type=CriterionType.METRIC,
        priority=1,
        step=CheckStep.COVERAGE,
        command=_py_command("print('anything')"),
    )
    result = evaluate_coverage(criterion, str(tmp_path))
    assert result.passed is True


def test_api_contract_evaluator_runs_given_command(tmp_path: Path) -> None:
    criterion = Criterion(
        id="openapi",
        type=CriterionType.OPENAPI,
        priority=1,
        step=CheckStep.API_CONTRACT,
        command=_py_command("import sys; sys.exit(0)"),
    )
    result = evaluate_api_contract(criterion, str(tmp_path))
    assert result.passed is True
    assert result.step == CheckStep.API_CONTRACT


def test_criterion_without_command_uses_step_default(tmp_path: Path) -> None:
    """A criterion with no `command` falls back to the step's default command.

    `tmp_path` has no `app/` directory (the default build command's target),
    so this only proves the default was *invoked* (a real command ran and
    returned a real exit code) rather than the evaluator raising for a
    missing command — it deliberately does not assert pass/fail.
    """
    criterion = Criterion(
        id="build-default",
        type=CriterionType.COMMAND,
        priority=1,
        step=CheckStep.BUILD,
    )
    result = evaluate_build(criterion, str(tmp_path))
    assert result.step == CheckStep.BUILD
    # A real command ran against tmp_path: compileall reports it can't find
    # the "app" target dir, proving the default was invoked for real rather
    # than the evaluator raising for a missing command.
    assert "app" in result.stdout


def test_registry_has_an_evaluator_for_every_pipeline_step() -> None:
    for step in (
        CheckStep.BUILD,
        CheckStep.LINT,
        CheckStep.EXISTING_TESTS,
        CheckStep.NEW_TESTS,
        CheckStep.MIGRATION,
        CheckStep.COVERAGE,
        CheckStep.API_CONTRACT,
    ):
        assert step in EVALUATOR_REGISTRY


def _git_init_repo(root: Path) -> None:
    """Initialize a committed git repo at `root` (deterministic identity)."""
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
    }
    subprocess.run(["git", "init", "-q"], cwd=root, check=True, env={**env})
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, env={**env})
    subprocess.run(
        ["git", "commit", "-q", "-m", "baseline"], cwd=root, check=True, env={**env}
    )


# --- required-file / feature-exists (T073) -------------------------------


def test_required_file_evaluator_passes_when_all_paths_exist(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "idempotency.py").write_text("x = 1\n")
    criterion = Criterion(
        id="feature-exists",
        type=CriterionType.COMMAND,
        priority=1,
        step=CheckStep.REQUIRED_FILE,
        source_paths=["app/idempotency.py"],
    )
    result = evaluate_required_file(criterion, str(tmp_path))

    assert result.passed is True
    assert result.step == CheckStep.REQUIRED_FILE
    assert result.exit_code == 0


def test_required_file_evaluator_fails_when_a_path_is_missing(tmp_path: Path) -> None:
    criterion = Criterion(
        id="feature-exists",
        type=CriterionType.COMMAND,
        priority=1,
        step=CheckStep.REQUIRED_FILE,
        params={"paths": ["app/idempotency.py", "app/missing.py"]},
    )
    result = evaluate_required_file(criterion, str(tmp_path))

    assert result.passed is False
    assert "missing" in result.stderr


def test_required_file_evaluator_fails_when_no_paths_configured(tmp_path: Path) -> None:
    criterion = Criterion(
        id="feature-exists",
        type=CriterionType.COMMAND,
        priority=1,
        step=CheckStep.REQUIRED_FILE,
    )
    result = evaluate_required_file(criterion, str(tmp_path))
    assert result.passed is False


# --- protected-files (T073) ----------------------------------------------


def test_protected_files_evaluator_passes_when_untouched(tmp_path: Path) -> None:
    (tmp_path / "auth.py").write_text("secret = 1\n")
    (tmp_path / "orders.py").write_text("orders = []\n")
    _git_init_repo(tmp_path)
    # Modify a non-protected file only.
    (tmp_path / "orders.py").write_text("orders = [1]\n")

    criterion = Criterion(
        id="protect-auth",
        type=CriterionType.GIT_POLICY,
        priority=1,
        step=CheckStep.PROTECTED_FILES,
        source_paths=["auth.py"],
    )
    result = evaluate_protected_files(criterion, str(tmp_path))

    assert result.passed is True
    assert result.step == CheckStep.PROTECTED_FILES


def test_protected_files_evaluator_fails_when_protected_file_modified(
    tmp_path: Path,
) -> None:
    (tmp_path / "auth.py").write_text("secret = 1\n")
    _git_init_repo(tmp_path)
    (tmp_path / "auth.py").write_text("secret = 2\n")

    criterion = Criterion(
        id="protect-auth",
        type=CriterionType.GIT_POLICY,
        priority=1,
        step=CheckStep.PROTECTED_FILES,
        params={"paths": ["auth.py"]},
    )
    result = evaluate_protected_files(criterion, str(tmp_path))

    assert result.passed is False
    assert "auth.py" in result.stderr


def test_protected_files_evaluator_fails_closed_outside_a_git_repo(
    tmp_path: Path,
) -> None:
    (tmp_path / "auth.py").write_text("secret = 1\n")
    criterion = Criterion(
        id="protect-auth",
        type=CriterionType.GIT_POLICY,
        priority=1,
        step=CheckStep.PROTECTED_FILES,
        source_paths=["auth.py"],
    )
    result = evaluate_protected_files(criterion, str(tmp_path))
    assert result.passed is False


# --- performance-vs-baseline (T073) --------------------------------------


def test_performance_evaluator_passes_when_lower_than_baseline(tmp_path: Path) -> None:
    criterion = Criterion(
        id="latency",
        type=CriterionType.METRIC,
        priority=1,
        step=CheckStep.PERFORMANCE,
        command=_py_command("print('latency_ms 42')"),
        params={"baseline": 50.0, "direction": "lower_is_better"},
    )
    result = evaluate_performance(criterion, str(tmp_path))

    assert result.passed is True
    assert result.step == CheckStep.PERFORMANCE


def test_performance_evaluator_fails_when_worse_than_baseline(tmp_path: Path) -> None:
    criterion = Criterion(
        id="latency",
        type=CriterionType.METRIC,
        priority=1,
        step=CheckStep.PERFORMANCE,
        command=_py_command("print('latency_ms 80')"),
        params={"baseline": 50.0, "direction": "lower_is_better"},
    )
    result = evaluate_performance(criterion, str(tmp_path))
    assert result.passed is False


def test_performance_evaluator_supports_higher_is_better(tmp_path: Path) -> None:
    criterion = Criterion(
        id="throughput",
        type=CriterionType.METRIC,
        priority=1,
        step=CheckStep.PERFORMANCE,
        command=_py_command("print('rps 1200')"),
        params={"baseline": 1000.0, "direction": "higher_is_better"},
    )
    result = evaluate_performance(criterion, str(tmp_path))
    assert result.passed is True


def test_performance_evaluator_fails_when_command_fails(tmp_path: Path) -> None:
    criterion = Criterion(
        id="latency",
        type=CriterionType.METRIC,
        priority=1,
        step=CheckStep.PERFORMANCE,
        command=_py_command("import sys; sys.exit(1)"),
        params={"baseline": 50.0},
    )
    result = evaluate_performance(criterion, str(tmp_path))
    assert result.passed is False


# --- architecture-conformance (T073) -------------------------------------


def test_architecture_evaluator_passes_on_conformant_command(tmp_path: Path) -> None:
    criterion = Criterion(
        id="arch",
        type=CriterionType.ARCHITECTURE,
        priority=1,
        step=CheckStep.ARCHITECTURE,
        command=_py_command("print('contracts kept'); import sys; sys.exit(0)"),
    )
    result = evaluate_architecture(criterion, str(tmp_path))

    assert result.passed is True
    assert result.step == CheckStep.ARCHITECTURE


def test_architecture_evaluator_fails_on_violation(tmp_path: Path) -> None:
    criterion = Criterion(
        id="arch",
        type=CriterionType.ARCHITECTURE,
        priority=1,
        step=CheckStep.ARCHITECTURE,
        command=_py_command("import sys; sys.exit(1)"),
    )
    result = evaluate_architecture(criterion, str(tmp_path))
    assert result.passed is False


def test_registry_covers_every_fr_001c_criterion_type() -> None:
    """Every FR-001c criterion type has a registered evaluator (T073)."""
    for step in (
        CheckStep.REQUIRED_FILE,
        CheckStep.PROTECTED_FILES,
        CheckStep.PERFORMANCE,
        CheckStep.ARCHITECTURE,
    ):
        assert step in EVALUATOR_REGISTRY


def test_fr_001c_extension_steps_stay_out_of_the_ordered_pipeline() -> None:
    """The new steps are registered but excluded from the demo pipeline."""
    from mergegate.acceptance.engine import PIPELINE_ORDER

    for step in (
        CheckStep.REQUIRED_FILE,
        CheckStep.PROTECTED_FILES,
        CheckStep.PERFORMANCE,
        CheckStep.ARCHITECTURE,
    ):
        assert step not in PIPELINE_ORDER


def test_register_evaluator_overrides_registry(tmp_path: Path) -> None:
    calls: list[str] = []

    def fake_evaluator(criterion, workspace):  # noqa: ANN001
        calls.append(criterion.id)
        from mergegate.models.verdict import CheckResult

        return CheckResult(
            criterion_id=criterion.id,
            step=CheckStep.BUILD,
            passed=True,
            exit_code=0,
            stdout="fake",
            stderr="",
            duration_ms=0,
        )

    original = EVALUATOR_REGISTRY[CheckStep.BUILD]
    try:
        register_evaluator(CheckStep.BUILD, fake_evaluator)
        criterion = Criterion(
            id="anything", type=CriterionType.COMMAND, priority=1, step=CheckStep.BUILD
        )
        result = EVALUATOR_REGISTRY[CheckStep.BUILD](criterion, str(tmp_path))
        assert result.stdout == "fake"
        assert calls == ["anything"]
    finally:
        register_evaluator(CheckStep.BUILD, original)
