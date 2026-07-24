"""Unit tests for the T027 run driver + T074 cost accounting.

These exercise the bounded attempt loop against a throwaway git repo and a
fake harness adapter (no network, no demo-repo): a passing attempt reaches the
merge gate with a recorded verdict and accumulated cost; repeated unchanged
failures stop as ``NO_PROGRESS``; a zero wall-clock budget stops immediately at
``TIMED_OUT`` (never ``SUCCESS``); and a harness that cannot run stops at
``NO_PROGRESS``.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import Path

import pytest

from mergegate.acceptance.commands import run_command
from mergegate.harness.base import HarnessAdapter, HarnessError, HarnessResult
from mergegate.models import (
    Budget,
    CheckStep,
    Contract,
    ContractMode,
    CostAccounting,
    Criterion,
    CriterionType,
    Policy,
    Run,
    RunStatus,
)
from mergegate.models.attempt import StructuredFeedback
from mergegate.orchestrator import nodes
from mergegate.orchestrator.nodes import RunContext, drive_run
from mergegate.workspace.worktree import Worktree, capture_diff

PY = sys.executable


class FakeAdapter(HarnessAdapter):
    """Writes a fixed file set into the worktree and reports fixed usage."""

    def __init__(
        self,
        files: Mapping[str, str],
        *,
        tokens: int = 100,
        model_calls: int = 1,
        usd: float = 0.5,
        fail: bool = False,
    ) -> None:
        self._files = files
        self._tokens = tokens
        self._model_calls = model_calls
        self._usd = usd
        self._fail = fail

    def propose_changes(
        self,
        objective: str,
        feedback: StructuredFeedback | None,
        workspace: Worktree,
    ) -> HarnessResult:
        if self._fail:
            raise HarnessError("fake harness could not run")
        for relative_path, contents in self._files.items():
            target = workspace.path / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(contents)
        diff = capture_diff(workspace)
        return HarnessResult(
            diff=diff.patch,
            changed_files=diff.changed_files,
            log="fake",
            tokens=self._tokens,
            model_calls=self._model_calls,
            usd=self._usd,
        )


@pytest.fixture()
def git_repo(tmp_path: Path) -> Path:
    """A minimal committed git repo to branch attempt worktrees from."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "seed.txt").write_text("seed\n")
    run_command(["git", "init"], cwd=repo)
    run_command(["git", "config", "user.email", "t@example.com"], cwd=repo)
    run_command(["git", "config", "user.name", "Test"], cwd=repo)
    run_command(["git", "add", "-A"], cwd=repo)
    run_command(["git", "commit", "-m", "seed"], cwd=repo)
    return repo


def _make_run(budgets: Budget) -> Run:
    return Run(
        id="run-test",
        workflow_id="wf-test",
        objective="do the thing",
        repo_ref="",
        status=RunStatus.RUNNING,
        budgets=budgets,
        current_attempt=0,
        cost=CostAccounting(),
    )


def test_policy_is_checked_before_validation_and_stops_retries(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events: list[tuple[str, dict]] = []
    run = _make_run(Budget(max_attempts=3, max_wall_clock_s=60, max_model_calls=3))
    run.repo_ref = str(git_repo)
    contract = _contract(
        f'"{sys.executable}" -c "from pathlib import Path; '
        "assert Path('protected/guard.py').exists()\""
    )
    monkeypatch.setattr(
        nodes,
        "get_adapter",
        lambda provider, **kwargs: FakeAdapter(
            {"protected/guard.py": "disabled = True\n"}
        ),
    )
    ctx = RunContext(
        run=run,
        contract=contract,
        policy=Policy(protected_paths=["protected/**"]),
        provider="fake",
        repo_ref=str(git_repo),
        worktrees_root=tmp_path / "worktrees",
        on_event=lambda kind, payload: events.append((kind, payload)),
    )

    drive_run(ctx)

    assert run.status == RunStatus.POLICY_BLOCKED
    assert run.attempts[0].verdict is None
    assert [kind for kind, _ in events].count("policy_block") == 1
    assert all(kind not in {"verdict", "retry", "gate"} for kind, _ in events)


def _contract(command: str) -> Contract:
    return Contract(
        id="c-1",
        run_id="run-test",
        mode=ContractMode.HYBRID,
        criteria=[
            Criterion(
                id="new-tests",
                type=CriterionType.COMMAND,
                priority=1,
                command=command,
                step=CheckStep.NEW_TESTS,
            )
        ],
        approved=True,
        frozen_hash="deadbeef",
    )


def _context(run: Run, repo: Path, contract: Contract) -> RunContext:
    return RunContext(
        run=run,
        contract=contract,
        provider="fake",
        repo_ref=str(repo),
        workspace_subdir=".",
        adapter_kwargs={},
    )


def _patch_adapter(monkeypatch: pytest.MonkeyPatch, adapter: FakeAdapter) -> None:
    monkeypatch.setattr(nodes, "get_adapter", lambda provider, **kwargs: adapter)


def test_passing_attempt_reaches_gate_with_verdict_and_cost(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = FakeAdapter({"feature.txt": "done\n"}, tokens=100, model_calls=1, usd=0.5)
    _patch_adapter(monkeypatch, adapter)

    run = _make_run(Budget(max_attempts=3, max_wall_clock_s=300, max_model_calls=20))
    contract = _contract(f'"{PY}" -c "pass"')
    drive_run(_context(run, git_repo, contract))

    assert run.status == RunStatus.AWAITING_GATE
    assert run.current_attempt == 1
    assert run.attempts[-1].verdict is not None
    assert run.attempts[-1].verdict.passed is True
    assert run.attempts[-1].verdict.acceptance_hash
    # T074: harness usage accumulated into the run's cost accounting.
    assert run.cost.model_calls == 1
    assert run.cost.tokens == 100
    assert run.cost.usd == 0.5


def test_identical_failing_attempts_stop_as_no_progress(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = FakeAdapter({"feature.txt": "done\n"}, model_calls=1)
    _patch_adapter(monkeypatch, adapter)

    run = _make_run(Budget(max_attempts=2, max_wall_clock_s=300, max_model_calls=20))
    contract = _contract(f'"{PY}" -c "raise SystemExit(1)"')
    drive_run(_context(run, git_repo, contract))

    assert run.status == RunStatus.NO_PROGRESS
    assert run.current_attempt == 2
    assert all(a.verdict is not None and not a.verdict.passed for a in run.attempts)
    assert run.cost.model_calls == 2


def test_zero_wall_clock_times_out_before_any_attempt(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = FakeAdapter({"feature.txt": "done\n"})
    _patch_adapter(monkeypatch, adapter)

    run = _make_run(Budget(max_attempts=3, max_wall_clock_s=0, max_model_calls=20))
    contract = _contract(f'"{PY}" -c "pass"')
    drive_run(_context(run, git_repo, contract))

    assert run.status == RunStatus.TIMED_OUT
    assert run.status != RunStatus.SUCCESS
    assert run.current_attempt == 0


def test_model_call_budget_stops_after_the_current_failed_attempt(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = FakeAdapter({"feature.txt": "done\n"}, model_calls=1)
    _patch_adapter(monkeypatch, adapter)

    run = _make_run(Budget(max_attempts=3, max_wall_clock_s=300, max_model_calls=1))
    contract = _contract(f'"{PY}" -c "raise SystemExit(1)"')
    drive_run(_context(run, git_repo, contract))

    assert run.status == RunStatus.EXHAUSTED
    assert run.current_attempt == 1
    assert run.attempts[0].verdict is not None
    assert run.cost.model_calls == 1


def test_harness_error_maps_to_no_progress(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = FakeAdapter({}, fail=True)
    _patch_adapter(monkeypatch, adapter)

    run = _make_run(Budget(max_attempts=3, max_wall_clock_s=300, max_model_calls=20))
    contract = _contract(f'"{PY}" -c "pass"')
    drive_run(_context(run, git_repo, contract))

    assert run.status == RunStatus.NO_PROGRESS
    assert run.status != RunStatus.SUCCESS
    assert run.undelivered_report is not None
    assert "fake harness could not run" in run.undelivered_report["reason"]
