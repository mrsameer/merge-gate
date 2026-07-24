"""T016b — Scripted, deterministic `HarnessAdapter` for tests and offline demos
(FR-034, FR-035, research.md R5).

Instead of driving a real coding harness (which needs a provider CLI, network,
and credentials), this adapter replays a *predetermined* change into the
attempt's worktree: either a unified diff (applied with `git apply`) or a
mapping of relative path -> new file contents (written directly). That makes
the whole orchestration loop exercisable end-to-end with zero external
dependencies and byte-for-byte reproducible results.

Consistent with `cursor.py`/`anthropic.py`, the returned diff is recovered
from git (`capture_diff`) after the change lands, not assumed from the input —
so `changed_files` reflects what actually hit disk. Usage is zeroed (no model
was called). If the scripted change cannot be applied, the harness effectively
"couldn't run", so it raises `HarnessError` (Principle IV) rather than
returning a misleading empty result.
"""

from __future__ import annotations

import tempfile
from collections.abc import Mapping
from pathlib import Path

from mergegate.acceptance.commands import run_command
from mergegate.harness.base import HarnessAdapter, HarnessError, HarnessResult
from mergegate.models.attempt import StructuredFeedback
from mergegate.workspace.worktree import Worktree, capture_diff

DEFAULT_LOG = "scripted harness: applied predetermined change"


class ScriptedHarnessAdapter(HarnessAdapter):
    """Replays a fixed diff or file set into the worktree (no model, no network).

    Args:
        changes: Either a unified-diff string applied with ``git apply``, or a
            mapping of worktree-relative path -> new file contents written
            directly. An empty diff/mapping is a legitimate no-op change.
        log: Canned log text surfaced on the resulting `HarnessResult`.
    """

    def __init__(
        self,
        changes: str | Mapping[str, str],
        *,
        log: str = DEFAULT_LOG,
    ) -> None:
        self._changes = changes
        self._log = log

    def propose_changes(
        self,
        objective: str,
        feedback: StructuredFeedback | None,
        workspace: Worktree,
    ) -> HarnessResult:
        if isinstance(self._changes, str):
            self._apply_patch(self._changes, workspace)
        else:
            self._write_files(self._changes, workspace)

        diff = capture_diff(workspace)
        return HarnessResult(
            diff=diff.patch,
            changed_files=diff.changed_files,
            log=self._log,
            tokens=0,
            model_calls=0,
            usd=0.0,
        )

    def _apply_patch(self, patch: str, workspace: Worktree) -> None:
        """Apply a unified diff to the worktree, raising on failure."""
        if not patch.strip():
            return

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".patch", delete=False, encoding="utf-8"
        ) as handle:
            handle.write(patch)
            patch_path = handle.name

        try:
            result = run_command(
                ["git", "apply", "--whitespace=nowarn", patch_path],
                cwd=workspace.path,
            )
        finally:
            Path(patch_path).unlink(missing_ok=True)

        if not result.succeeded:
            raise HarnessError(
                f"scripted harness could not apply patch: {result.stderr.strip()}"
            )

    def _write_files(self, files: Mapping[str, str], workspace: Worktree) -> None:
        """Write each relative path -> contents into the worktree, raising on error."""
        try:
            for relative_path, contents in files.items():
                target = workspace.path / relative_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(contents, encoding="utf-8")
        except OSError as exc:
            raise HarnessError(
                f"scripted harness could not write files: {exc}"
            ) from exc
