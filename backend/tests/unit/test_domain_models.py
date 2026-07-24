"""Domain model tests for T006 — Pydantic models from data-model.md.

Encodes the field shapes and enum constraints for Run, Attempt, Contract,
Criterion, Verdict, CheckResult, Policy, Budget, CostAccounting, and
StructuredFeedback exactly as specified in
`specs/001-mergegate-control-plane/data-model.md`, so the models stay a
faithful, reviewable realization of that design rather than drifting ad hoc.

Invalid-value tests deliberately pass strings that aren't valid enum members
to prove the runtime validation rejects them; `cast` tells pyright to trust
that on those specific lines, since the whole point is to check what pydantic
does with an input the type checker would otherwise never allow through.
"""

from typing import cast

import pytest
from pydantic import ValidationError

from mergegate.models import (
    Attempt,
    Budget,
    CheckResult,
    CheckStep,
    Contract,
    ContractMode,
    CostAccounting,
    Criterion,
    CriterionType,
    PassFail,
    Policy,
    Run,
    RunStatus,
    StructuredFeedback,
    Verdict,
)


def test_budget_requires_all_three_limits() -> None:
    budget = Budget(max_attempts=5, max_wall_clock_s=1800, max_model_calls=40)
    assert budget.max_attempts == 5
    assert budget.max_wall_clock_s == 1800
    assert budget.max_model_calls == 40


def test_cost_accounting_defaults_to_zero() -> None:
    cost = CostAccounting()
    assert cost.tokens == 0
    assert cost.model_calls == 0
    assert cost.usd == 0.0


def test_criterion_type_rejects_unknown_value() -> None:
    with pytest.raises(ValidationError):
        Criterion(
            id="task-tests", type=cast(CriterionType, "not-a-real-type"), priority=1
        )


def test_criterion_accepts_each_documented_type() -> None:
    for criterion_type in CriterionType:
        criterion = Criterion(id=f"c-{criterion_type}", type=criterion_type, priority=1)
        assert criterion.type == criterion_type


def test_criterion_command_fields() -> None:
    criterion = Criterion(
        id="task-tests",
        type=CriterionType.COMMAND,
        priority=1,
        command="pytest tests/test_orders.py",
        expected_exit_code=0,
        baseline_expected=PassFail.FAIL,
        result_expected=PassFail.PASS,
    )
    assert criterion.command == "pytest tests/test_orders.py"
    assert criterion.baseline_expected == PassFail.FAIL
    assert criterion.result_expected == PassFail.PASS


def test_contract_defaults_to_hybrid_mode_and_unapproved() -> None:
    criterion = Criterion(id="coverage", type=CriterionType.METRIC, priority=2)
    contract = Contract(id="c1", run_id="r1", criteria=[criterion])
    assert contract.mode == ContractMode.HYBRID
    assert contract.approved is False
    assert contract.frozen_hash is None
    assert contract.criteria == [criterion]


def test_contract_rejects_unknown_mode() -> None:
    with pytest.raises(ValidationError):
        Contract(id="c1", run_id="r1", mode=cast(ContractMode, "guessed"), criteria=[])


def test_check_result_step_rejects_unknown_value() -> None:
    with pytest.raises(ValidationError):
        CheckResult(
            criterion_id="task-tests",
            step=cast(CheckStep, "not-a-step"),
            passed=True,
            exit_code=0,
            stdout="",
            stderr="",
            duration_ms=10,
        )


def test_check_result_records_pipeline_step_outcome() -> None:
    check = CheckResult(
        criterion_id="task-tests",
        step=CheckStep.NEW_TESTS,
        passed=True,
        exit_code=0,
        stdout="2 passed",
        stderr="",
        duration_ms=1200,
        baseline_result=PassFail.FAIL,
    )
    assert check.step == CheckStep.NEW_TESTS
    assert check.baseline_result == PassFail.FAIL


def test_verdict_bundles_checks_and_acceptance_input() -> None:
    check = CheckResult(
        criterion_id="task-tests",
        step=CheckStep.NEW_TESTS,
        passed=True,
        exit_code=0,
        stdout="",
        stderr="",
        duration_ms=500,
    )
    verdict = Verdict(
        attempt_id="a1",
        passed=True,
        checks=[check],
        acceptance_hash="abc123",
        acceptance_input={
            "commit_sha": "deadbeef",
            "validation_config": {"pipeline": "build,lint,tests"},
            "tool_versions": {"pytest": "8.3.5"},
            "env_fingerprint": "py3.11-linux",
        },
    )
    assert verdict.passed is True
    assert verdict.checks[0].step == CheckStep.NEW_TESTS
    assert verdict.replay_of is None


def test_structured_feedback_fields() -> None:
    feedback = StructuredFeedback(
        criterion="task-tests",
        command="pytest tests/test_orders.py",
        exit_code=1,
        failure_signature="AssertionError:test_idempotent_order",
        first_failing_location="tests/test_orders.py:42",
        attempt=1,
    )
    assert feedback.attempt == 1
    assert feedback.exit_code == 1


def test_attempt_nests_verdict_and_feedback_optionally() -> None:
    attempt_without_verdict = Attempt(
        id="a1",
        run_id="r1",
        index=1,
        worktree_path="/tmp/worktrees/a1",
        branch="attempt/a1",
        diff="",
        changed_files=[],
        harness_log="",
    )
    assert attempt_without_verdict.verdict is None
    assert attempt_without_verdict.feedback is None
    assert attempt_without_verdict.changed_files == []


def test_run_accepts_terminal_and_non_terminal_status_values() -> None:
    budget = Budget(max_attempts=3, max_wall_clock_s=600, max_model_calls=10)
    for status in RunStatus:
        run = Run(
            id="r1",
            workflow_id="w1",
            objective="Make POST /orders idempotent",
            repo_ref="demo-repo@base",
            status=status,
            budgets=budget,
            current_attempt=0,
            cost=CostAccounting(),
        )
        assert run.status == status


def test_run_rejects_unknown_status() -> None:
    budget = Budget(max_attempts=3, max_wall_clock_s=600, max_model_calls=10)
    with pytest.raises(ValidationError):
        Run(
            id="r1",
            workflow_id="w1",
            objective="Make POST /orders idempotent",
            repo_ref="demo-repo@base",
            status=cast(RunStatus, "not-a-real-status"),
            budgets=budget,
            current_attempt=0,
            cost=CostAccounting(),
        )


def test_run_defaults_attempts_to_empty_list() -> None:
    budget = Budget(max_attempts=3, max_wall_clock_s=600, max_model_calls=10)
    run = Run(
        id="r1",
        workflow_id="w1",
        objective="Make POST /orders idempotent",
        repo_ref="demo-repo@base",
        status=RunStatus.RUNNING,
        budgets=budget,
        current_attempt=0,
        cost=CostAccounting(),
    )
    assert run.attempts == []


def test_policy_holds_protected_paths_and_forbidden_patterns() -> None:
    policy = Policy(
        protected_paths=["app/auth/**", "tests/acceptance/**"],
        forbidden_diff_patterns=["pytest.mark.skip", "eslint-disable"],
    )
    assert "app/auth/**" in policy.protected_paths
    assert "pytest.mark.skip" in policy.forbidden_diff_patterns
