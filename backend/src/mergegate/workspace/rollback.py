"""Clean terminal rollback and honest undelivered reports (US3/T042)."""

from __future__ import annotations

from mergegate.acceptance.commands import run_command
from mergegate.models import Run
from mergegate.workspace.worktree import Worktree, discard_worktree


def rollback_run(
    run: Run,
    *,
    active_worktree: Worktree | None,
    reason: str,
    baseline_status: str | None = None,
) -> dict:
    """Discard the active workspace and record exactly what was not delivered."""
    if active_worktree is not None:
        discard_worktree(active_worktree)

    current_status = run_command(["git", "status", "--porcelain"], cwd=run.repo_ref)
    current_porcelain = current_status.stdout
    report = {
        "terminal_state": run.status.value,
        "reason": reason,
        "attempts_completed": run.current_attempt,
        "delivered": False,
        "base_repository_clean": current_status.succeeded
        and not current_porcelain.strip(),
        "baseline_preserved": current_status.succeeded
        and (baseline_status is None or current_porcelain == baseline_status),
    }
    run.undelivered_report = report
    return report
