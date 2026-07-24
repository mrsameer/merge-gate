"""Unit tests for the headless Gemini CLI harness adapter.

The real Gemini CLI is an agent that can use a Google-account OAuth session or
an API key. These tests use a tiny local executable instead, so they prove the
adapter's isolated-worktree, prompt, JSON-usage, and error contracts without a
network call or a credential.
"""

from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

import pytest

from mergegate.acceptance.commands import run_command
from mergegate.harness.base import HarnessError, HarnessResult
from mergegate.harness.gemini import GEMINI_API_KEY_ENV_VAR, GeminiHarnessAdapter
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


@pytest.fixture()
def fake_gemini(tmp_path: Path) -> Path:
    script = tmp_path / "fake_gemini.py"
    script.write_text(
        textwrap.dedent(
            """
            import json
            import os
            import pathlib
            import sys

            args_file = os.environ.get("FAKE_GEMINI_ARGS_FILE")
            if args_file:
                pathlib.Path(args_file).write_text(json.dumps(sys.argv[1:]))
            write_file = os.environ.get("FAKE_GEMINI_WRITE_FILE")
            if write_file:
                pathlib.Path(write_file).write_text(
                    os.environ.get("FAKE_GEMINI_WRITE_CONTENT", "")
                )
            print(json.dumps({"stats": {"models": {"gemini-2.5-pro": {
                "tokens": {"input": 100, "output": 23}, "api": {"requests": 2}
            }}}}))
            sys.exit(int(os.environ.get("FAKE_GEMINI_EXIT_CODE", "0")))
            """
        )
    )
    return script


def test_propose_changes_edits_the_isolated_worktree_and_maps_usage(
    monkeypatch: pytest.MonkeyPatch, workspace: Worktree, fake_gemini: Path
) -> None:
    monkeypatch.setenv("FAKE_GEMINI_WRITE_FILE", str(workspace.path / "new_file.py"))
    monkeypatch.setenv("FAKE_GEMINI_WRITE_CONTENT", "print('added')\n")
    adapter = GeminiHarnessAdapter(
        executable=[sys.executable, str(fake_gemini)], model="gemini-2.5-pro"
    )

    result = adapter.propose_changes("add a new file", None, workspace)

    assert isinstance(result, HarnessResult)
    assert "new_file.py" in result.changed_files
    assert "print('added')" in result.diff
    assert result.tokens == 123
    assert result.model_calls == 2


def test_uses_headless_yolo_json_mode_and_includes_model_and_feedback(
    monkeypatch: pytest.MonkeyPatch,
    workspace: Worktree,
    fake_gemini: Path,
    tmp_path: Path,
) -> None:
    args_file = tmp_path / "argv.json"
    monkeypatch.setenv("FAKE_GEMINI_ARGS_FILE", str(args_file))
    feedback = StructuredFeedback(
        criterion="existing_tests",
        command="pytest",
        exit_code=1,
        failure_signature="AssertionError: idempotency key missing",
        attempt=1,
    )
    adapter = GeminiHarnessAdapter(
        executable=[sys.executable, str(fake_gemini)], model="gemini-2.5-pro"
    )

    adapter.propose_changes("make POST /orders idempotent", feedback, workspace)

    argv = json.loads(args_file.read_text())
    assert argv[argv.index("-p") + 1].startswith("make POST /orders idempotent")
    assert "existing_tests" in argv[argv.index("-p") + 1]
    assert ["-m", "gemini-2.5-pro"] == argv[argv.index("-m") : argv.index("-m") + 2]
    assert "--output-format" in argv
    assert argv[argv.index("--output-format") + 1] == "json"
    assert "--yolo" in argv
    assert "--skip-trust" in argv


def test_api_key_is_forwarded_only_as_environment_not_argv(
    monkeypatch: pytest.MonkeyPatch,
    workspace: Worktree,
    fake_gemini: Path,
    tmp_path: Path,
) -> None:
    args_file = tmp_path / "argv.json"
    monkeypatch.setenv("FAKE_GEMINI_ARGS_FILE", str(args_file))
    adapter = GeminiHarnessAdapter(
        executable=[sys.executable, str(fake_gemini)], api_key="super-secret-key"
    )

    adapter.propose_changes("objective", None, workspace)

    assert "super-secret-key" not in json.loads(args_file.read_text())
    assert GEMINI_API_KEY_ENV_VAR == "GEMINI_API_KEY"


def test_missing_executable_and_failed_cli_raise_harness_error(
    monkeypatch: pytest.MonkeyPatch, workspace: Worktree, fake_gemini: Path
) -> None:
    with pytest.raises(HarnessError, match="not found"):
        GeminiHarnessAdapter(executable="not-a-real-gemini").propose_changes(
            "objective", None, workspace
        )

    monkeypatch.setenv("FAKE_GEMINI_EXIT_CODE", "1")
    with pytest.raises(HarnessError, match="exited with 1"):
        GeminiHarnessAdapter(
            executable=[sys.executable, str(fake_gemini)]
        ).propose_changes("objective", None, workspace)
