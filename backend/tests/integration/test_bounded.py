"""US3: exhausted and no-progress runs leave an honest, clean baseline."""

from __future__ import annotations

from pathlib import Path

import pytest

from mergegate.acceptance.commands import run_command
from mergegate.models import (
    Budget,
    Contract,
    CostAccounting,
    Criterion,
    CriterionType,
    PassFail,
    Run,
    RunStatus,
)
from mergegate.models.enums import CheckStep
from mergegate.orchestrator import nodes
from mergegate.orchestrator.nodes import RunContext, drive_run


def _git(repo: Path, *args: str) -> None:
    result = run_command(["git", *args], cwd=repo)
    assert result.succeeded, result.stderr


@pytest.fixture()
def base_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "target"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "baseline")
    return repo


def _contract(run_id: str) -> Contract:
    return Contract(
        id="contract-1",
        run_id=run_id,
        approved=True,
        frozen_hash="frozen",
        criteria=[
            Criterion(
                id="task-tests",
                type=CriterionType.COMMAND,
                priority=1,
                command='python -c "import sys; sys.exit(1)"',
                baseline_expected=PassFail.FAIL,
                result_expected=PassFail.PASS,
                step=CheckStep.NEW_TESTS,
            )
        ],
    )


class _RecordingNoOpHarness:
    def __init__(self) -> None:
        self.feedback = []

    def propose_changes(self, objective, feedback, workspace):  # noqa: ANN001
        from mergegate.harness.base import HarnessResult

        self.feedback.append(feedback)
        return HarnessResult(diff="", log="no change")


def _run(base_repo: Path, budgets: Budget, monkeypatch: pytest.MonkeyPatch):
    run = Run(
        id="run-us3",
        workflow_id="workflow",
        objective="make the task pass",
        repo_ref=str(base_repo),
        status=RunStatus.RUNNING,
        budgets=budgets,
        current_attempt=0,
        cost=CostAccounting(),
    )
    harness = _RecordingNoOpHarness()
    monkeypatch.setattr(nodes, "get_adapter", lambda _provider, **_kwargs: harness)
    drive_run(
        RunContext(
            run=run,
            contract=_contract(run.id),
            provider="recording",
            repo_ref=str(base_repo),
            worktrees_root=base_repo.parent / "worktrees",
        )
    )
    return run, harness


def test_exhaustion_discards_attempt_workspace_preserves_baseline_and_reports(
    base_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run, _harness = _run(
        base_repo,
        Budget(max_attempts=1, max_wall_clock_s=30, max_model_calls=10),
        monkeypatch,
    )

    assert run.status == RunStatus.EXHAUSTED
    assert run.undelivered_report is not None
    assert run.undelivered_report["reason"] == "attempt budget exhausted"
    assert run.undelivered_report["baseline_preserved"] is True
    assert all(not Path(attempt.worktree_path).exists() for attempt in run.attempts)
    assert run_command(["git", "status", "--porcelain"], cwd=base_repo).stdout == ""


def test_identical_failures_stop_as_no_progress_and_feed_the_next_plan(
    base_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run, harness = _run(
        base_repo,
        Budget(max_attempts=3, max_wall_clock_s=30, max_model_calls=10),
        monkeypatch,
    )

    assert run.status == RunStatus.NO_PROGRESS
    assert run.current_attempt == 2
    assert harness.feedback[1].criterion == "task-tests"
    assert harness.feedback[1].command == 'python -c "import sys; sys.exit(1)"'
    assert harness.feedback[1].first_failing_location is None
    assert run.undelivered_report is not None
    assert run.undelivered_report["reason"] == "no progress detected"
    assert run.undelivered_report["baseline_preserved"] is True
    assert all(not Path(attempt.worktree_path).exists() for attempt in run.attempts)
