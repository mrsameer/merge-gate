from __future__ import annotations

from pathlib import Path
from typing import Any

from mergegate.models import Run
from mergegate.workspace.worktree import discard_worktree


def rollback_run(
    *,
    run: Run,
    repo_path: Path,
    worktrees: list[Path],
    reason: str,
) -> dict[str, Any]:
    for worktree_path in worktrees:
        if worktree_path.exists():
            discard_worktree(worktree_path, repo_path)

    return {
        "delivered": False,
        "reason": reason,
        "attempts": run.current_attempt,
        "objective": run.objective,
        "message": (
            f"Run could not deliver after {run.current_attempt} attempt(s): {reason}"
        ),
    }
