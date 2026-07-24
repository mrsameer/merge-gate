"""Unit coverage for the reusable US3 bounded-autonomy policies."""

from __future__ import annotations

from mergegate.acceptance.feedback import build_failure_feedback
from mergegate.models import CheckResult, CheckStep, RunStatus
from mergegate.orchestrator.budgets import BudgetGuard
from mergegate.orchestrator.no_progress import NoProgressDetector, failure_signature


def _failed_check() -> CheckResult:
    return CheckResult(
        criterion_id="task-tests",
        step=CheckStep.NEW_TESTS,
        passed=False,
        exit_code=1,
        stdout="tests/test_orders.py:42: AssertionError: expected 201",
        stderr="",
        duration_ms=10,
    )


def test_failure_feedback_preserves_the_actionable_failure_details() -> None:
    feedback = build_failure_feedback(
        [_failed_check()],
        commands={"task-tests": "pytest tests/test_orders.py -q"},
        attempt=2,
    )

    assert feedback.criterion == "task-tests"
    assert feedback.command == "pytest tests/test_orders.py -q"
    assert feedback.exit_code == 1
    assert feedback.first_failing_location == "tests/test_orders.py:42"
    assert feedback.failure_signature
    assert feedback.attempt == 2


def test_budget_guard_stops_before_a_new_attempt_or_model_call() -> None:
    guard = BudgetGuard(
        max_attempts=2, max_wall_clock_s=30, max_model_calls=3, now=lambda: 12
    )
    guard.start()

    assert guard.terminal_status(attempts=1, model_calls=2) is None
    assert guard.terminal_status(attempts=2, model_calls=2) == RunStatus.EXHAUSTED
    assert guard.terminal_status(attempts=1, model_calls=3) == RunStatus.EXHAUSTED


def test_budget_guard_reports_wall_clock_timeout() -> None:
    now = iter((10.0, 15.0))
    guard = BudgetGuard(
        max_attempts=2, max_wall_clock_s=4, max_model_calls=3, now=lambda: next(now)
    )
    guard.start()

    assert guard.terminal_status(attempts=0, model_calls=0) == RunStatus.TIMED_OUT


def test_no_progress_requires_same_signature_and_unchanged_diff() -> None:
    detector = NoProgressDetector()
    signature = failure_signature(_failed_check())

    assert detector.observe(signature, "diff-a") is False
    assert detector.observe(signature, "diff-b") is False
    assert detector.observe(signature, "diff-b") is True
