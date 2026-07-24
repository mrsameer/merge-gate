"""T014 — Git worktree manager: per-attempt isolation and rollback (FR-011,
FR-014, FR-015, research.md R4).

Every attempt runs in its own disposable `git worktree` on a fresh branch, so
a failed or abandoned attempt can be discarded without ever touching the base
repo (Principle IV). This module owns that lifecycle plus the two safety
rails around it:

* **Command allowlist.** A `Worktree` only runs commands whose executable is
  on its `allowed_commands` set; anything else is rejected before a process
  is ever spawned.
* **Timeout.** Execution is delegated to `acceptance.commands.run_command`,
  which already enforces a per-command wall-clock budget and never raises for
  a timeout or missing executable — it returns a `CommandResult` instead so a
  blocked or slow attempt command becomes a recorded failure, not a crash.

Diff capture stages the worktree's full working tree (`git add -A`) before
diffing against the commit the worktree branched from, so new/untracked
files the harness created are included in `Attempt.diff` and
`Attempt.changed_files`, not just modifications to already-tracked files.
"""

from __future__ import annotations

import shlex
import shutil
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from mergegate.acceptance.commands import DEFAULT_TIMEOUT_S, CommandResult, run_command

# Executables an attempt is permitted to run inside its worktree. Deliberately
# narrow: enough to install, build, lint, type-check, and test a project
# without granting the harness a general-purpose shell.
DEFAULT_ALLOWED_COMMANDS: frozenset[str] = frozenset(
    {
        "git",
        "python",
        "python3",
        "pip",
        "uv",
        "pytest",
        "ruff",
        "pyright",
        "node",
        "npm",
        "npx",
        "pnpm",
        "yarn",
        "make",
    }
)


class WorktreeError(RuntimeError):
    """Raised when a git worktree operation (create/discard) fails."""


class CommandNotAllowedError(WorktreeError):
    """Raised when a command's executable is not on the worktree's allowlist."""


@dataclass(frozen=True)
class Worktree:
    """A disposable git worktree bound to one attempt (data-model.md § Attempt)."""

    path: Path
    branch: str
    base_repo: Path
    base_commit: str
    allowed_commands: frozenset[str] = field(default=DEFAULT_ALLOWED_COMMANDS)


@dataclass(frozen=True)
class WorktreeDiff:
    """Captured change set for an attempt (`Attempt.diff` / `changed_files`)."""

    patch: str
    changed_files: list[str]


def _normalize_argv(command: Sequence[str] | str) -> list[str]:
    if isinstance(command, str):
        return shlex.split(command)
    return [str(part) for part in command]


def create_worktree(
    base_repo: str | Path,
    *,
    branch: str,
    base_ref: str = "HEAD",
    worktrees_root: str | Path | None = None,
    allowed_commands: Iterable[str] = DEFAULT_ALLOWED_COMMANDS,
) -> Worktree:
    """Create a fresh git worktree for one attempt.

    `base_ref` is resolved to a concrete commit up front so the worktree's
    starting point stays fixed even if the base repo's branch moves on while
    the attempt is in flight, and so `capture_diff` always diffs against the
    true starting point regardless of whether the attempt commits its work.

    Raises:
        WorktreeError: If `base_ref` cannot be resolved or `git worktree add`
            fails (e.g. `branch` already exists).
    """
    base_repo_path = Path(base_repo).resolve()

    resolved = run_command(["git", "rev-parse", base_ref], cwd=base_repo_path)
    if not resolved.succeeded:
        raise WorktreeError(
            f"cannot resolve base ref {base_ref!r}: {resolved.stderr.strip()}"
        )
    base_commit = resolved.stdout.strip()

    slug = branch.replace("/", "-")
    if worktrees_root is not None:
        target = Path(worktrees_root) / slug
        target.parent.mkdir(parents=True, exist_ok=True)
    else:
        target = Path(tempfile.mkdtemp(prefix="mergegate-worktrees-")) / slug

    created = run_command(
        ["git", "worktree", "add", "-b", branch, str(target), base_commit],
        cwd=base_repo_path,
    )
    if not created.succeeded:
        raise WorktreeError(f"git worktree add failed: {created.stderr.strip()}")

    return Worktree(
        path=target,
        branch=branch,
        base_repo=base_repo_path,
        base_commit=base_commit,
        allowed_commands=frozenset(allowed_commands),
    )


def run_in_worktree(
    worktree: Worktree,
    command: Sequence[str] | str,
    *,
    timeout_s: float | None = DEFAULT_TIMEOUT_S,
    extra_env: Mapping[str, str] | None = None,
) -> CommandResult:
    """Run `command` inside `worktree`, enforcing the allowlist and timeout.

    Raises:
        CommandNotAllowedError: If the command's executable is not in
            `worktree.allowed_commands`. The process is never spawned.
    """
    argv = _normalize_argv(command)
    executable = Path(argv[0]).name
    if executable not in worktree.allowed_commands:
        raise CommandNotAllowedError(
            f"command {executable!r} is not on this worktree's allowlist"
        )

    return run_command(
        argv, cwd=worktree.path, timeout_s=timeout_s, extra_env=extra_env
    )


def capture_diff(worktree: Worktree) -> WorktreeDiff:
    """Capture the attempt's full change set relative to its starting commit.

    Stages the working tree first (`git add -A`) so new/untracked files are
    included, then diffs the staged tree against `base_commit` — the commit
    the worktree branched from — so committed and uncommitted attempt changes
    are both captured identically.
    """
    run_command(["git", "add", "-A"], cwd=worktree.path)

    diff = run_command(
        ["git", "diff", "--cached", worktree.base_commit], cwd=worktree.path
    )
    names = run_command(
        ["git", "diff", "--cached", "--name-only", worktree.base_commit],
        cwd=worktree.path,
    )
    changed_files = [line for line in names.stdout.splitlines() if line.strip()]

    return WorktreeDiff(patch=diff.stdout, changed_files=changed_files)


def discard_worktree(worktree: Worktree, *, delete_branch: bool = True) -> None:
    """Remove `worktree` and its branch, leaving the base repo untouched
    (FR-015 rollback).

    Falls back to a plain filesystem removal plus `git worktree prune` if
    `git worktree remove` itself fails (e.g. the directory was already
    deleted out-of-band), so discard is never blocked by a stale git worktree
    registration.
    """
    removed = run_command(
        ["git", "worktree", "remove", "--force", str(worktree.path)],
        cwd=worktree.base_repo,
    )
    if not removed.succeeded and worktree.path.exists():
        shutil.rmtree(worktree.path, ignore_errors=True)
        run_command(["git", "worktree", "prune"], cwd=worktree.base_repo)

    if delete_branch:
        run_command(["git", "branch", "-D", worktree.branch], cwd=worktree.base_repo)
