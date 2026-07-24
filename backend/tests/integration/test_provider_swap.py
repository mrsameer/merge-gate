"""US8 integration proof: provider config swaps without workflow changes."""

from __future__ import annotations

from pathlib import Path

import pytest

from mergegate.acceptance.commands import run_command
from mergegate.config.providers import resolve_agent_provider
from mergegate.config.settings import Settings
from mergegate.harness.base import HarnessAdapter, HarnessResult
from mergegate.models import (
    AgentRole,
    Budget,
    Contract,
    ContractMode,
    CostAccounting,
    Criterion,
    CriterionType,
    Node,
    NodeConfig,
    NodeType,
    Run,
    RunStatus,
    Workflow,
)
from mergegate.orchestrator import nodes
from mergegate.orchestrator.nodes import RunContext, run_execution_node


class RecordingAdapter(HarnessAdapter):
    def __init__(self, provider: str, calls: list[str]) -> None:
        self.provider = provider
        self.calls = calls

    def propose_changes(self, objective, feedback, workspace):  # noqa: ANN001
        self.calls.append(self.provider)
        target = workspace.path / f"{self.provider}.txt"
        target.write_text(f"{objective}\n", encoding="utf-8")
        diff = run_command(["git", "diff", "--", target.name], cwd=workspace.path)
        return HarnessResult(
            diff=diff.stdout,
            changed_files=[target.name],
            log=f"{self.provider} handled objective",
        )


def _git(args: list[str], cwd: Path) -> None:
    result = run_command(["git", *args], cwd=cwd)
    assert result.succeeded, result.stderr


@pytest.fixture()
def base_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(["init", "-q"], repo)
    _git(["config", "user.email", "test@example.com"], repo)
    _git(["config", "user.name", "Test"], repo)
    (repo / "README.md").write_text("baseline\n", encoding="utf-8")
    _git(["add", "-A"], repo)
    _git(["commit", "-q", "-m", "baseline"], repo)
    return repo


def _workflow() -> Workflow:
    return Workflow(
        id="same-workflow",
        name="Same workflow",
        version="1.0.0",
        nodes=[
            Node(id="input", type=NodeType.INPUT, name="Input"),
            Node(
                id="execution",
                type=NodeType.AGENT,
                name="Execution",
                config=NodeConfig(role=AgentRole.EXECUTION),
            ),
            Node(id="success", type=NodeType.SUCCESS, name="Success"),
            Node(id="stop", type=NodeType.STOP, name="Stop"),
        ],
        edges=[],
    )


def _settings(provider: str) -> Settings:
    return Settings(
        provider=provider,
        model=f"{provider}-model",
        max_attempts=1,
        max_wall_clock_s=30,
        max_model_calls=2,
    )


def _context(
    repo: Path, provider: str, run_id: str, worktrees_root: Path
) -> RunContext:
    run = Run(
        id=run_id,
        workflow_id="same-workflow",
        objective="implement the same objective",
        repo_ref=str(repo),
        status=RunStatus.RUNNING,
        budgets=Budget(max_attempts=1, max_wall_clock_s=30, max_model_calls=2),
        current_attempt=0,
        cost=CostAccounting(),
    )
    contract = Contract(
        id=f"contract-{run_id}",
        run_id=run_id,
        mode=ContractMode.HYBRID,
        criteria=[
            Criterion(
                id="provider-proof",
                type=CriterionType.COMMAND,
                priority=1,
                command="true",
            )
        ],
    )
    return RunContext(
        run=run,
        contract=contract,
        provider=provider,
        repo_ref=str(repo),
        worktrees_root=worktrees_root,
    )


def test_provider_selected_from_config_swaps_without_workflow_change(
    monkeypatch: pytest.MonkeyPatch, base_repo: Path, tmp_path: Path
) -> None:
    workflow = _workflow()
    workflow_before = workflow.model_dump_json()
    calls: list[str] = []
    monkeypatch.setattr(
        nodes,
        "get_adapter",
        lambda provider, **_kwargs: RecordingAdapter(provider, calls),
    )

    for index, configured_provider in enumerate(("aider", "codex"), start=1):
        selection = resolve_agent_provider(
            workflow,
            AgentRole.EXECUTION,
            settings=_settings(configured_provider),
        )
        attempt, _ = run_execution_node(
            _context(
                base_repo,
                selection.provider,
                f"run-{index}",
                tmp_path / f"worktrees-{index}",
            ),
            1,
            None,
        )
        assert configured_provider in attempt.changed_files[0]

    assert calls == ["aider", "codex"]
    assert workflow.model_dump_json() == workflow_before
