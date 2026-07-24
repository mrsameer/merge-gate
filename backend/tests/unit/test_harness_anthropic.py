"""Unit tests for T016b — the Claude Agent SDK adapter `AnthropicHarnessAdapter`
(FR-034, FR-035, research.md R5).

The adapter drives the official `claude-agent-sdk` `query` loop inside the
attempt's worktree and recovers the diff from git afterwards. These tests inject
a *fake* `query` (a real async agent stand-in built from the SDK's own message
dataclasses) so the whole contract — prompt construction from objective +
feedback, diff recovery, usage mapping, and the failure-to-invoke paths — is
exercised with no network access and no real API key. Only genuine live runs
need a real key.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import Any

import pytest
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeSDKError,
    CLINotFoundError,
    ResultMessage,
    TextBlock,
)

from mergegate.acceptance.commands import run_command
from mergegate.harness.anthropic import (
    API_KEY_ENV_VAR,
    FALLBACK_API_KEY_ENV_VAR,
    AnthropicHarnessAdapter,
)
from mergegate.harness.base import HarnessError, HarnessResult
from mergegate.models.attempt import StructuredFeedback
from mergegate.workspace.worktree import Worktree, create_worktree


def _git(args: list[str], cwd: Path) -> None:
    result = run_command(["git", *args], cwd=cwd)
    assert result.succeeded, result.stderr


@pytest.fixture()
def base_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "base-repo"
    repo.mkdir()
    _git(["init", "-q"], cwd=repo)
    _git(["config", "user.email", "test@example.com"], cwd=repo)
    _git(["config", "user.name", "Test"], cwd=repo)
    (repo / "app.py").write_text("print('hello')\n")
    _git(["add", "-A"], cwd=repo)
    _git(["commit", "-q", "-m", "initial"], cwd=repo)
    return repo


@pytest.fixture()
def workspace(base_repo: Path, tmp_path: Path) -> Worktree:
    return create_worktree(
        base_repo, branch="mergegate/attempt-1", worktrees_root=tmp_path / "worktrees"
    )


def _result_message(
    *, tokens_in: int = 0, tokens_out: int = 0, turns: int = 0, usd: float = 0.0
) -> ResultMessage:
    return ResultMessage(
        subtype="success",
        duration_ms=1,
        duration_api_ms=1,
        is_error=False,
        num_turns=turns,
        session_id="session-1",
        total_cost_usd=usd,
        usage={"input_tokens": tokens_in, "output_tokens": tokens_out},
        result="done",
    )


class FakeQuery:
    """A stand-in for `claude_agent_sdk.query`.

    Records the prompt/options it was called with, optionally writes a file into
    the agent's cwd (simulating an edit the real agent would make on disk), then
    yields a fixed sequence of SDK messages.
    """

    def __init__(
        self,
        messages: Sequence[Any],
        *,
        write: tuple[str, str] | None = None,
    ) -> None:
        self.messages = messages
        self.write = write
        self.prompt: str | None = None
        self.options: Any = None

    def __call__(self, *, prompt: str, options: Any) -> AsyncIterator[Any]:
        self.prompt = prompt
        self.options = options

        async def _run() -> AsyncIterator[Any]:
            if self.write is not None:
                relative_path, contents = self.write
                (Path(options.cwd) / relative_path).write_text(contents)
            for message in self.messages:
                yield message

        return _run()


def test_missing_api_key_raises_harness_error(
    monkeypatch: pytest.MonkeyPatch, workspace: Worktree
) -> None:
    monkeypatch.delenv(API_KEY_ENV_VAR, raising=False)
    monkeypatch.delenv(FALLBACK_API_KEY_ENV_VAR, raising=False)
    fake = FakeQuery([])
    adapter = AnthropicHarnessAdapter(query_fn=fake)

    with pytest.raises(HarnessError, match=API_KEY_ENV_VAR):
        adapter.propose_changes("do the thing", None, workspace)

    # The agent was never invoked.
    assert fake.prompt is None


def test_fallback_api_key_env_var_is_accepted(
    monkeypatch: pytest.MonkeyPatch, workspace: Worktree
) -> None:
    monkeypatch.delenv(API_KEY_ENV_VAR, raising=False)
    monkeypatch.setenv(FALLBACK_API_KEY_ENV_VAR, "fallback-key")
    fake = FakeQuery([_result_message()])
    adapter = AnthropicHarnessAdapter(query_fn=fake)

    adapter.propose_changes("objective", None, workspace)

    assert fake.prompt == "objective"
    assert fake.options.env[API_KEY_ENV_VAR] == "fallback-key"


def test_propose_changes_captures_diff_and_maps_usage(
    workspace: Worktree,
) -> None:
    fake = FakeQuery(
        [
            AssistantMessage(content=[TextBlock("Editing the file.")], model="claude"),
            _result_message(tokens_in=100, tokens_out=23, turns=2, usd=0.05),
        ],
        write=("new_file.py", "print('added')\n"),
    )
    adapter = AnthropicHarnessAdapter(api_key="test-key", query_fn=fake)

    result = adapter.propose_changes("add a new file", None, workspace)

    assert isinstance(result, HarnessResult)
    assert "new_file.py" in result.changed_files
    assert "print('added')" in result.diff
    assert result.tokens == 123
    assert result.model_calls == 2
    assert result.usd == 0.05
    assert "Editing the file." in result.log


def test_prompt_embeds_objective_and_prior_feedback(workspace: Worktree) -> None:
    fake = FakeQuery([_result_message()])
    adapter = AnthropicHarnessAdapter(api_key="test-key", query_fn=fake)

    feedback = StructuredFeedback(
        criterion="existing_tests",
        command="pytest",
        exit_code=1,
        failure_signature="AssertionError: idempotency key missing",
        attempt=1,
    )
    adapter.propose_changes("make POST /orders idempotent", feedback, workspace)

    assert fake.prompt is not None
    assert "make POST /orders idempotent" in fake.prompt
    assert "existing_tests" in fake.prompt
    assert "AssertionError: idempotency key missing" in fake.prompt


def test_no_change_run_returns_empty_diff_not_error(workspace: Worktree) -> None:
    fake = FakeQuery([_result_message()])
    adapter = AnthropicHarnessAdapter(api_key="test-key", query_fn=fake)

    result = adapter.propose_changes("do nothing useful", None, workspace)

    assert result.diff == ""
    assert result.changed_files == []


def test_cli_not_found_raises_harness_error(workspace: Worktree) -> None:
    def raising_query(*, prompt: str, options: Any) -> AsyncIterator[Any]:
        async def _run() -> AsyncIterator[Any]:
            raise CLINotFoundError()
            yield  # pragma: no cover - makes this an async generator

        return _run()

    adapter = AnthropicHarnessAdapter(api_key="test-key", query_fn=raising_query)

    with pytest.raises(HarnessError):
        adapter.propose_changes("objective", None, workspace)


def test_sdk_error_raises_harness_error(workspace: Worktree) -> None:
    def raising_query(*, prompt: str, options: Any) -> AsyncIterator[Any]:
        async def _run() -> AsyncIterator[Any]:
            raise ClaudeSDKError("boom")
            yield  # pragma: no cover - makes this an async generator

        return _run()

    adapter = AnthropicHarnessAdapter(api_key="test-key", query_fn=raising_query)

    with pytest.raises(HarnessError, match="Claude Agent SDK could not be invoked"):
        adapter.propose_changes("objective", None, workspace)
