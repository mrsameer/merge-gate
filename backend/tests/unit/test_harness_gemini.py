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
from mergegate.harness.gemini import (
    GEMINI_API_KEY_ENV_VAR,
    GEMINI_AUTH_ENV_VARS,
    GeminiHarnessAdapter,
    RequestThrottle,
    _parse_usage,
)
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
            config_file = os.environ.get("FAKE_GEMINI_CONFIG_FILE")
            if config_file:
                home = pathlib.Path(os.environ["GEMINI_CLI_HOME"])
                pathlib.Path(config_file).write_text(
                    (home / "settings.json").read_text()
                )
            auth_file = os.environ.get("FAKE_GEMINI_AUTH_FILE")
            if auth_file:
                names = [
                    "GEMINI_API_KEY",
                    "GOOGLE_GENAI_USE_VERTEXAI",
                    "GOOGLE_GENAI_USE_GCA",
                    "GOOGLE_CLOUD_PROJECT",
                    "GOOGLE_CLOUD_LOCATION",
                ]
                pathlib.Path(auth_file).write_text(
                    json.dumps({name: os.environ.get(name) for name in names})
                )
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
    assert result.usd == pytest.approx(0.000355)


def test_parse_usage_estimates_flash_cost_from_cached_and_output_tokens() -> None:
    stdout = json.dumps(
        {
            "stats": {
                "models": {
                    "gemini-2.5-flash": {
                        "tokens": {
                            "input": 90_000,
                            "prompt": 100_000,
                            "cached": 10_000,
                            "candidates": 20_000,
                            "total": 120_000,
                        },
                        "api": {"totalRequests": 1},
                    }
                }
            }
        }
    )

    tokens, model_calls, usd = _parse_usage(stdout)

    assert tokens == 120_000
    assert model_calls == 1
    assert usd == pytest.approx(0.0773)


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


def test_forwards_vertex_auth_environment(
    monkeypatch: pytest.MonkeyPatch,
    workspace: Worktree,
    fake_gemini: Path,
    tmp_path: Path,
) -> None:
    env_file = tmp_path / "gemini-auth.json"
    monkeypatch.setenv("FAKE_GEMINI_AUTH_FILE", str(env_file))
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "asia-south1")

    adapter = GeminiHarnessAdapter(executable=[sys.executable, str(fake_gemini)])
    adapter.propose_changes("objective", None, workspace)

    assert json.loads(env_file.read_text()) == {
        "GEMINI_API_KEY": None,
        "GOOGLE_GENAI_USE_VERTEXAI": "true",
        "GOOGLE_GENAI_USE_GCA": None,
        "GOOGLE_CLOUD_PROJECT": "test-project",
        "GOOGLE_CLOUD_LOCATION": "asia-south1",
    }
    assert "GOOGLE_GENAI_USE_VERTEXAI" in GEMINI_AUTH_ENV_VARS


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


def test_throttles_back_to_back_gemini_requests(
    monkeypatch: pytest.MonkeyPatch, workspace: Worktree, fake_gemini: Path
) -> None:
    """A provider rate limit is respected before issuing another model call."""
    timestamps = iter([100.0, 100.0, 101.0, 105.0])
    waits: list[float] = []
    throttle = RequestThrottle(clock=lambda: next(timestamps), sleeper=waits.append)
    adapter = GeminiHarnessAdapter(
        executable=[sys.executable, str(fake_gemini)],
        min_request_interval_s=5.0,
        throttle=throttle,
    )

    adapter.propose_changes("first", None, workspace)
    adapter.propose_changes("second", None, workspace)

    assert waits == [4.0]


def test_limits_gemini_internal_turns_and_runtime(
    monkeypatch: pytest.MonkeyPatch,
    workspace: Worktree,
    fake_gemini: Path,
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "gemini-settings.json"
    monkeypatch.setenv("FAKE_GEMINI_CONFIG_FILE", str(config_file))
    adapter = GeminiHarnessAdapter(
        executable=[sys.executable, str(fake_gemini)],
        max_turns=4,
        max_time_minutes=2,
    )

    adapter.propose_changes("objective", None, workspace)

    assert json.loads(config_file.read_text()) == {
        "runConfig": {"maxTurns": 4, "maxTimeMinutes": 2}
    }
