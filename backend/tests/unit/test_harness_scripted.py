"""Unit tests for T016b — the deterministic `ScriptedHarnessAdapter` and the
provider registry (FR-034, FR-035, research.md R5).

`ScriptedHarnessAdapter` replays a predetermined change (a unified diff or a
path -> contents mapping) into a real throwaway git worktree, then recovers the
diff from git exactly like the live adapters. These tests need no network and
no credentials.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mergegate.acceptance.commands import run_command
from mergegate.harness.base import HarnessError, HarnessResult
from mergegate.harness.registry import (
    AnthropicHarnessAdapter,
    CursorAdapter,
    ScriptedHarnessAdapter,
    get_adapter,
)
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


def test_apply_patch_captures_diff_and_changed_files(workspace: Worktree) -> None:
    patch = (
        "diff --git a/app.py b/app.py\n"
        "index 0000000..1111111 100644\n"
        "--- a/app.py\n"
        "+++ b/app.py\n"
        "@@ -1 +1 @@\n"
        "-print('hello')\n"
        "+print('goodbye')\n"
    )

    adapter = ScriptedHarnessAdapter(patch)
    result = adapter.propose_changes("change the greeting", None, workspace)

    assert isinstance(result, HarnessResult)
    assert result.changed_files == ["app.py"]
    assert "print('goodbye')" in result.diff
    assert result.tokens == 0
    assert result.model_calls == 0
    assert result.usd == 0.0
    assert result.log
    # The change actually landed on disk.
    assert (workspace.path / "app.py").read_text() == "print('goodbye')\n"


def test_write_files_mapping_captures_new_files(workspace: Worktree) -> None:
    adapter = ScriptedHarnessAdapter(
        {"pkg/new_module.py": "VALUE = 42\n"},
        log="wrote a module",
    )

    result = adapter.propose_changes("add a module", None, workspace)

    assert "pkg/new_module.py" in result.changed_files
    assert "VALUE = 42" in result.diff
    assert result.log == "wrote a module"
    assert (workspace.path / "pkg" / "new_module.py").read_text() == "VALUE = 42\n"


def test_empty_diff_is_a_legitimate_noop(workspace: Worktree) -> None:
    adapter = ScriptedHarnessAdapter("")

    result = adapter.propose_changes("do nothing", None, workspace)

    assert result.diff == ""
    assert result.changed_files == []


def test_bad_patch_raises_harness_error(workspace: Worktree) -> None:
    adapter = ScriptedHarnessAdapter("this is not a valid unified diff\n")

    with pytest.raises(HarnessError):
        adapter.propose_changes("apply garbage", None, workspace)


def test_registry_resolves_known_providers(workspace: Worktree) -> None:
    assert isinstance(get_adapter("cursor"), CursorAdapter)
    assert isinstance(get_adapter("anthropic"), AnthropicHarnessAdapter)
    assert isinstance(
        get_adapter("scripted", changes={"f.py": "x = 1\n"}),
        ScriptedHarnessAdapter,
    )


def test_registry_forwards_kwargs(workspace: Worktree) -> None:
    # kwargs reach the adapter constructor: a custom log surfaces on the result.
    adapter = get_adapter("scripted", changes="", log="canned log")
    result = adapter.propose_changes("noop", None, workspace)

    assert result.log == "canned log"


def test_registry_unknown_provider_raises_value_error() -> None:
    with pytest.raises(ValueError, match="unknown provider"):
        get_adapter("does-not-exist")
