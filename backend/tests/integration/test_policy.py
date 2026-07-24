"""US5 integration: policy violations halt before deterministic verdict."""

from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import Path

import pytest

from mergegate.acceptance.commands import run_command
from mergegate.harness.base import HarnessAdapter, HarnessResult
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


class PolicyFixtureAdapter(HarnessAdapter):
    def __init__(self, files: Mapping[str, str]) -> None:
        self._files = files

    def propose_changes(
        self,
        objective: str,
        feedback: StructuredFeedback | None,
        workspace: Worktree,
    ) -> HarnessResult:
        for relative_path, contents in self._files.items():
            target = workspace.path / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(contents)
        diff = capture_diff(workspace)
        return HarnessResult(
            diff=diff.patch,
            changed_files=diff.changed_files,
            log="policy fixture",
        )


@pytest.fixture()
def policy_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app" / "auth").mkdir(parents=True)
    (repo / "app" / "auth" / "security.py").write_text("TOKEN = 'safe'\n")
    (repo / "passing.py").write_text("VALUE = 1\n")
    run_command(["git", "init"], cwd=repo)
    run_command(["git", "config", "user.email", "t@example.com"], cwd=repo)
    run_command(["git", "config", "user.name", "Test"], cwd=repo)
    run_command(["git", "add", "-A"], cwd=repo)
    run_command(["git", "commit", "-m", "seed"], cwd=repo)
    return repo


def _context(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    files: Mapping[str, str],
    policy: Policy,
    events: list[tuple[str, dict]],
) -> RunContext:
    monkeypatch.setattr(
        nodes, "get_adapter", lambda provider, **kwargs: PolicyFixtureAdapter(files)
    )
    run = Run(
        id="run-policy",
        workflow_id="wf-policy",
        objective="attempt a forbidden change",
        repo_ref=str(repo),
        status=RunStatus.RUNNING,
        budgets=Budget(max_attempts=2, max_wall_clock_s=60, max_model_calls=2),
        current_attempt=0,
        cost=CostAccounting(),
    )
    contract = Contract(
        id="contract-policy",
        run_id=run.id,
        mode=ContractMode.HYBRID,
        criteria=[
            Criterion(
                id="passing",
                type=CriterionType.COMMAND,
                priority=1,
                step=CheckStep.EXISTING_TESTS,
                command=f'"{PY}" -c "import passing; assert passing.VALUE == 1"',
            )
        ],
        approved=True,
        frozen_hash="frozen",
    )
    return RunContext(
        run=run,
        contract=contract,
        policy=policy,
        provider="fake",
        repo_ref=str(repo),
        worktrees_root=repo.parent / "worktrees",
        on_event=lambda kind, payload: events.append((kind, payload)),
    )


@pytest.mark.parametrize(
    ("files", "policy", "expected_offender"),
    [
        (
            {"app/auth/security.py": "TOKEN = 'weakened'\n"},
            Policy(protected_paths=["app/auth/**"]),
            "app/auth/security.py",
        ),
        (
            {
                "tests/test_orders.py": (
                    "import pytest\n\n"
                    "@pytest.mark.skip(reason='avoid failure')\n"
                    "def test_orders(): ...\n"
                )
            },
            Policy(forbidden_diff_patterns=["pytest.mark.skip"]),
            "pytest.mark.skip",
        ),
    ],
)
def test_policy_violation_blocks_before_verdict_and_names_offender(
    policy_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    files: Mapping[str, str],
    policy: Policy,
    expected_offender: str,
) -> None:
    events: list[tuple[str, dict]] = []
    ctx = _context(policy_repo, monkeypatch, files, policy, events)

    drive_run(ctx)

    assert ctx.run.status == RunStatus.POLICY_BLOCKED
    assert ctx.run.current_attempt == 1
    assert len(ctx.run.attempts) == 1
    assert ctx.run.attempts[0].verdict is None
    policy_event = next(payload for kind, payload in events if kind == "policy_block")
    assert policy_event["path_or_pattern"] == expected_offender
    assert expected_offender in policy_event["message"]
    event_names = [kind for kind, _ in events]
    assert "verdict" not in event_names
    assert event_names.index("policy_block") < event_names.index("terminal")
