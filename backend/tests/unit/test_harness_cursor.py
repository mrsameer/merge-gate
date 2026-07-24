"""Unit tests for T016 — the headless `cursor-agent` CLI adapter (FR-034,
FR-035, research.md R5).

`CursorAdapter` is the default `HarnessAdapter`: it shells out to `cursor-agent`
in non-interactive print mode inside the attempt's worktree, then recovers the
diff from git rather than the CLI's own output, since the CLI edits files on
disk directly. These tests exercise that contract against a fake CLI script
(controlled via env vars) rather than the real `cursor-agent`, so they're
deterministic and need no network access or credentials.
"""

from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

import pytest

from mergegate.acceptance.commands import run_command
from mergegate.harness.base import HarnessError, HarnessResult
from mergegate.harness.cursor import API_KEY_ENV_VAR, CursorAdapter
from mergegate.models.attempt import StructuredFeedback
from mergegate.workspace.worktree import Worktree, create_worktree


def _git(args: list[str], cwd: Path) -> None:
    result = run_command(["git", *args], cwd=cwd)
    assert result.succeeded, result.stderr


@pytest.fixture()
def base_repo(tmp_path: Path) -> Path:
    """A throwaway git repo with a single tracked file and commit."""
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


@pytest.fixture()
def fake_cursor_agent(tmp_path: Path) -> Path:
    """A stand-in `cursor-agent` driven entirely by env vars.

    Optionally writes a file into its cwd (simulating an edit the real CLI
    would make on disk), records the argv it was invoked with, prints a JSON
    usage line to stdout, and exits with a configurable code.
    """
    script = tmp_path / "fake_cursor_agent.py"
    script.write_text(
        textwrap.dedent(
            """
            import json
            import os
            import pathlib
            import sys

            args_file = os.environ.get("FAKE_CURSOR_ARGS_FILE")
            if args_file:
                pathlib.Path(args_file).write_text(json.dumps(sys.argv[1:]))

            write_file = os.environ.get("FAKE_CURSOR_WRITE_FILE")
            if write_file:
                pathlib.Path(write_file).write_text(
                    os.environ.get("FAKE_CURSOR_WRITE_CONTENT", "")
                )

            print(
                json.dumps(
                    {
                        "usage": {
                            "tokens": int(os.environ.get("FAKE_CURSOR_TOKENS", "0")),
                            "model_calls": int(
                                os.environ.get("FAKE_CURSOR_MODEL_CALLS", "0")
                            ),
                            "usd": float(os.environ.get("FAKE_CURSOR_USD", "0")),
                        }
                    }
                )
            )
            sys.exit(int(os.environ.get("FAKE_CURSOR_EXIT_CODE", "0")))
            """
        )
    )
    return script


def test_missing_api_key_raises_harness_error(
    monkeypatch: pytest.MonkeyPatch, workspace: Worktree
) -> None:
    monkeypatch.delenv(API_KEY_ENV_VAR, raising=False)
    adapter = CursorAdapter(executable=[sys.executable, "unused.py"])

    with pytest.raises(HarnessError, match=API_KEY_ENV_VAR):
        adapter.propose_changes("do the thing", None, workspace)


def test_missing_executable_raises_harness_error(workspace: Worktree) -> None:
    adapter = CursorAdapter(
        executable="definitely-not-a-real-cursor-agent-binary", api_key="key"
    )

    with pytest.raises(HarnessError):
        adapter.propose_changes("do the thing", None, workspace)


def test_propose_changes_captures_diff_from_git(
    monkeypatch: pytest.MonkeyPatch, workspace: Worktree, fake_cursor_agent: Path
) -> None:
    monkeypatch.setenv("FAKE_CURSOR_WRITE_FILE", str(workspace.path / "new_file.py"))
    monkeypatch.setenv("FAKE_CURSOR_WRITE_CONTENT", "print('added')\n")
    monkeypatch.setenv("FAKE_CURSOR_TOKENS", "123")
    monkeypatch.setenv("FAKE_CURSOR_MODEL_CALLS", "2")
    monkeypatch.setenv("FAKE_CURSOR_USD", "0.05")

    adapter = CursorAdapter(
        executable=[sys.executable, str(fake_cursor_agent)], api_key="test-key"
    )

    result = adapter.propose_changes("add a new file", None, workspace)

    assert isinstance(result, HarnessResult)
    assert "new_file.py" in result.changed_files
    assert "print('added')" in result.diff
    assert result.tokens == 123
    assert result.model_calls == 2
    assert result.usd == 0.05
    assert "usage" in result.log


def test_propose_changes_returns_empty_diff_when_no_change(
    monkeypatch: pytest.MonkeyPatch, workspace: Worktree, fake_cursor_agent: Path
) -> None:
    adapter = CursorAdapter(
        executable=[sys.executable, str(fake_cursor_agent)], api_key="test-key"
    )

    result = adapter.propose_changes("do nothing useful", None, workspace)

    assert result.diff == ""
    assert result.changed_files == []


def test_propose_changes_embeds_prior_feedback_in_prompt(
    monkeypatch: pytest.MonkeyPatch,
    workspace: Worktree,
    fake_cursor_agent: Path,
    tmp_path: Path,
) -> None:
    args_file = tmp_path / "argv.json"
    monkeypatch.setenv("FAKE_CURSOR_ARGS_FILE", str(args_file))

    feedback = StructuredFeedback(
        criterion="existing_tests",
        command="pytest",
        exit_code=1,
        failure_signature="AssertionError: idempotency key missing",
        attempt=1,
    )

    adapter = CursorAdapter(
        executable=[sys.executable, str(fake_cursor_agent)], api_key="test-key"
    )
    adapter.propose_changes("make POST /orders idempotent", feedback, workspace)

    argv = json.loads(args_file.read_text())
    prompt = argv[argv.index("-p") + 1]

    assert "make POST /orders idempotent" in prompt
    assert "existing_tests" in prompt
    assert "AssertionError: idempotency key missing" in prompt


def test_api_key_is_not_leaked_into_argv(
    monkeypatch: pytest.MonkeyPatch,
    workspace: Worktree,
    fake_cursor_agent: Path,
    tmp_path: Path,
) -> None:
    args_file = tmp_path / "argv.json"
    monkeypatch.setenv("FAKE_CURSOR_ARGS_FILE", str(args_file))

    adapter = CursorAdapter(
        executable=[sys.executable, str(fake_cursor_agent)],
        api_key="super-secret-key",
    )
    adapter.propose_changes("objective", None, workspace)

    argv = json.loads(args_file.read_text())
    assert "super-secret-key" not in argv
