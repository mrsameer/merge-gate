"""Unit tests for T027 — four-role loop node wiring."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mergegate.harness.base import HarnessAdapter, HarnessResult
from mergegate.models import (
    AgentRole,
    Contract,
    Criterion,
    CriterionType,
    Run,
    RunStatus,
)
from mergegate.orchestrator.nodes import FourRoleNodeRunner


class RecordingHarness(HarnessAdapter):
    calls: list[dict] = []

    def propose_changes(
        self,
        *,
        objective: str,
        feedback: dict | None,
        workspace: str,
    ) -> HarnessResult:
        type(self).calls.append(
            {"objective": objective, "feedback": feedback, "workspace": workspace}
        )
        return HarnessResult(
            diff="",
            changed_files=["app/orders/router.py"],
            log="harness executed",
            model_calls=0,
        )


@pytest.fixture
def repo_path() -> Path:
    return Path(__file__).resolve().parents[3] / "demo-repo"


@pytest.fixture
def sample_run() -> Run:
    return Run(
        id="run-1",
        workflow_id="default-four-role-loop",
        objective="Add idempotent order creation",
        repo_ref="demo-repo",
        status=RunStatus.RUNNING,
        contract=Contract(
            id="contract-1",
            run_id="run-1",
            approved=True,
            frozen_hash="abc123",
            criteria=[
                Criterion(
                    id="existing-tests",
                    type=CriterionType.COMMAND,
                    command="python -c \"print('ok')\"",
                    expected_exit_code=0,
                )
            ],
        ),
    )


def test_success_criteria_node_generates_contract(repo_path: Path) -> None:
    runner = FourRoleNodeRunner(harness=RecordingHarness(), repo_path=repo_path)
    run = Run(
        id="run-1",
        workflow_id="default-four-role-loop",
        objective="Add idempotent order creation",
        repo_ref="demo-repo",
        status=RunStatus.AWAITING_GATE,
    )

    result = runner.run_success_criteria(run)

    assert result.role == AgentRole.SUCCESS_CRITERIA
    assert result.node_id == "success_criteria"
    assert result.output["contract"].run_id == "run-1"
    assert len(result.output["contract"].criteria) >= 1


def test_execute_attempt_runs_planning_execution_validation_in_order(
    repo_path: Path, sample_run: Run, tmp_path: Path
) -> None:
    RecordingHarness.calls = []
    runner = FourRoleNodeRunner(harness=RecordingHarness(), repo_path=repo_path)
    worktree = tmp_path / "wt"
    worktree.mkdir()
    (worktree / "app" / "orders").mkdir(parents=True)
    (worktree / "app" / "orders" / "router.py").write_text(
        '"""Baseline stub"""\n', encoding="utf-8"
    )

    with patch(
        "mergegate.orchestrator.nodes.run_acceptance_engine",
        return_value=MagicMock(passed=True, acceptance_hash="hash-1", checks=[]),
    ) as mock_engine:
        ctx = runner.execute_attempt(
            run=sample_run,
            worktree_path=worktree,
            attempt_id="attempt-1",
            attempt_index=1,
        )

    roles = [result.role for result in ctx.node_results]
    assert roles == [
        AgentRole.PLANNING,
        AgentRole.EXECUTION,
        AgentRole.VALIDATION,
    ]
    assert RecordingHarness.calls
    mock_engine.assert_called_once()
    assert ctx.verdict is not None
    assert ctx.plan


def test_execution_delegates_to_harness_not_acceptance_engine(
    repo_path: Path, sample_run: Run, tmp_path: Path
) -> None:
    harness = MagicMock(spec=HarnessAdapter)
    harness.prepare_acceptance_tests.return_value = HarnessResult(
        diff="", changed_files=[], log="", model_calls=0
    )
    harness.propose_changes.return_value = HarnessResult(
        diff="",
        changed_files=[],
        log="ok",
        model_calls=0,
    )
    runner = FourRoleNodeRunner(harness=harness, repo_path=repo_path)
    worktree = tmp_path / "wt"
    worktree.mkdir()

    with patch("mergegate.orchestrator.nodes.run_acceptance_engine") as mock_engine:
        mock_engine.return_value = MagicMock(
            passed=True, acceptance_hash="hash-1", checks=[]
        )
        runner.execute_attempt(
            run=sample_run,
            worktree_path=worktree,
            attempt_id="attempt-1",
            attempt_index=1,
        )

    harness.propose_changes.assert_called_once()
    assert mock_engine.call_count == 1


def test_validation_delegates_to_acceptance_engine(
    repo_path: Path, sample_run: Run, tmp_path: Path
) -> None:
    runner = FourRoleNodeRunner(harness=RecordingHarness(), repo_path=repo_path)
    worktree = tmp_path / "wt"
    worktree.mkdir()

    with patch(
        "mergegate.orchestrator.nodes.run_acceptance_engine",
        return_value=MagicMock(passed=False, acceptance_hash="hash-2", checks=[]),
    ) as mock_engine:
        ctx = runner.execute_attempt(
            run=sample_run,
            worktree_path=worktree,
            attempt_id="attempt-1",
            attempt_index=1,
        )

    validation = ctx.node_results[-1]
    assert validation.role == AgentRole.VALIDATION
    assert validation.node_id == "validation"
    assert validation.status == "failed"
    mock_engine.assert_called_once_with(
        attempt_id="attempt-1",
        contract=sample_run.contract,
        workspace=worktree,
    )
