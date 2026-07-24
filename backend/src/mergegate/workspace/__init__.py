"""Git worktree lifecycle for per-attempt isolation (Constitution Principle IV).

Every attempt executes in a disposable git worktree on its own branch, with a
command allowlist and timeout, so a failed or abandoned attempt can be
discarded cleanly without ever mutating the base repo.
"""

from mergegate.workspace.worktree import (
    DEFAULT_ALLOWED_COMMANDS,
    CommandNotAllowedError,
    Worktree,
    WorktreeDiff,
    WorktreeError,
    capture_diff,
    create_worktree,
    discard_worktree,
    run_in_worktree,
)

__all__ = [
    "DEFAULT_ALLOWED_COMMANDS",
    "CommandNotAllowedError",
    "Worktree",
    "WorktreeDiff",
    "WorktreeError",
    "capture_diff",
    "create_worktree",
    "discard_worktree",
    "run_in_worktree",
]
