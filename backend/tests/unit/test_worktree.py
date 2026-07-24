"""Unit tests for T014 — the git worktree manager (FR-011, FR-014, FR-015).

Per-attempt isolation is the mechanism behind bounded autonomy: each attempt
gets its own disposable git worktree on a fresh branch, commands run against
it are constrained to an allowlist with a timeout, the resulting diff can be
captured, and discarding it must leave the base repo untouched (research.md
R4). These tests exercise a real git repo in a tmp dir rather than mocking
git, since the whole point of this module is correct git plumbing.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from mergegate.acceptance.commands import TIMEOUT_EXIT_CODE, run_command
from mergegate.workspace.worktree import (
    CommandNotAllowedError,
    WorktreeError,
    capture_diff,
    create_worktree,
    discard_worktree,
    run_in_worktree,
)


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
    (repo / "app.py").write_text("def add(a, b):\n    return a + b\n")
    _git(["add", "."], cwd=repo)
    _git(["commit", "-q", "-m", "initial"], cwd=repo)
    return repo


def test_create_worktree_checks_out_a_fresh_branch(
    base_repo: Path, tmp_path: Path
) -> None:
    worktree = create_worktree(
        base_repo, branch="mergegate/attempt-1", worktrees_root=tmp_path / "worktrees"
    )

    assert worktree.path.is_dir()
    assert (worktree.path / "app.py").exists()

    current_branch = run_command(["git", "branch", "--show-current"], cwd=worktree.path)
    assert current_branch.stdout.strip() == "mergegate/attempt-1"

    discard_worktree(worktree)


def test_create_worktree_leaves_base_repo_untouched(
    base_repo: Path, tmp_path: Path
) -> None:
    original_branch = run_command(
        ["git", "branch", "--show-current"], cwd=base_repo
    ).stdout.strip()

    worktree = create_worktree(
        base_repo, branch="mergegate/attempt-2", worktrees_root=tmp_path / "worktrees"
    )

    current_branch = run_command(
        ["git", "branch", "--show-current"], cwd=base_repo
    ).stdout.strip()
    assert current_branch == original_branch

    status = run_command(["git", "status", "--porcelain"], cwd=base_repo)
    assert status.stdout == ""

    discard_worktree(worktree)


def test_create_worktree_raises_on_unresolvable_base_ref(
    base_repo: Path, tmp_path: Path
) -> None:
    with pytest.raises(WorktreeError):
        create_worktree(
            base_repo,
            branch="mergegate/attempt-3",
            base_ref="not-a-real-ref",
            worktrees_root=tmp_path / "worktrees",
        )


def test_run_in_worktree_executes_allowed_command(
    base_repo: Path, tmp_path: Path
) -> None:
    worktree = create_worktree(
        base_repo, branch="mergegate/attempt-4", worktrees_root=tmp_path / "worktrees"
    )

    result = run_in_worktree(worktree, ["git", "status", "--porcelain"])

    assert result.succeeded is True

    discard_worktree(worktree)


def test_run_in_worktree_blocks_disallowed_command(
    base_repo: Path, tmp_path: Path
) -> None:
    worktree = create_worktree(
        base_repo, branch="mergegate/attempt-5", worktrees_root=tmp_path / "worktrees"
    )
    marker = worktree.path / "should-not-exist.txt"

    with pytest.raises(CommandNotAllowedError):
        run_in_worktree(worktree, ["touch", str(marker)])

    assert not marker.exists()

    discard_worktree(worktree)


def test_run_in_worktree_enforces_timeout(base_repo: Path, tmp_path: Path) -> None:
    worktree = create_worktree(
        base_repo,
        branch="mergegate/attempt-6",
        worktrees_root=tmp_path / "worktrees",
        allowed_commands=frozenset({"git", Path(sys.executable).name}),
    )

    result = run_in_worktree(
        worktree,
        [sys.executable, "-c", "import time; time.sleep(2)"],
        timeout_s=0.05,
    )

    assert result.timed_out is True
    assert result.exit_code == TIMEOUT_EXIT_CODE

    discard_worktree(worktree)


def test_capture_diff_reports_modified_and_new_files(
    base_repo: Path, tmp_path: Path
) -> None:
    worktree = create_worktree(
        base_repo, branch="mergegate/attempt-7", worktrees_root=tmp_path / "worktrees"
    )

    (worktree.path / "app.py").write_text("def add(a, b):\n    return a + b + 0\n")
    (worktree.path / "new_test.py").write_text("def test_add():\n    assert True\n")

    diff = capture_diff(worktree)

    assert set(diff.changed_files) == {"app.py", "new_test.py"}
    assert "new_test.py" in diff.patch
    assert "+    return a + b + 0" in diff.patch

    discard_worktree(worktree)


def test_capture_diff_after_commit_still_reflects_full_change(
    base_repo: Path, tmp_path: Path
) -> None:
    worktree = create_worktree(
        base_repo, branch="mergegate/attempt-8", worktrees_root=tmp_path / "worktrees"
    )

    (worktree.path / "new_file.py").write_text("value = 1\n")
    _git(["add", "."], cwd=worktree.path)
    _git(["commit", "-q", "-m", "attempt change"], cwd=worktree.path)

    diff = capture_diff(worktree)

    assert "new_file.py" in diff.changed_files

    discard_worktree(worktree)


def test_discard_worktree_removes_path_and_branch(
    base_repo: Path, tmp_path: Path
) -> None:
    worktree = create_worktree(
        base_repo, branch="mergegate/attempt-9", worktrees_root=tmp_path / "worktrees"
    )
    path = worktree.path

    discard_worktree(worktree)

    assert not path.exists()

    remaining_branch = run_command(
        ["git", "branch", "--list", "mergegate/attempt-9"], cwd=base_repo
    )
    assert remaining_branch.stdout.strip() == ""

    worktree_list = run_command(["git", "worktree", "list"], cwd=base_repo)
    assert str(path) not in worktree_list.stdout
