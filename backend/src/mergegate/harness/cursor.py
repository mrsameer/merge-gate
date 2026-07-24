"""T016 — Cursor CLI headless adapter implementing `HarnessAdapter` (FR-034,
FR-035, research.md R5).

`cursor-agent` is the default coding harness: invoked in non-interactive
print mode (`-p`) inside the attempt's worktree, it edits files and runs
commands directly on disk, so the diff it produced is recovered afterwards
from git (`workspace.capture_diff`) rather than parsed out of the CLI's own
output. The CLI's stdout is only trusted for a trailing JSON usage line
(tokens/model-calls/cost) when present; anything else is just log text.

Authentication is a bare `CURSOR_API_KEY` — missing it means the harness
can't even be invoked, so it raises `HarnessError` up front rather than
spawning a process doomed to fail (Principle IV: a crash must never be
recorded as a successful, if empty, attempt).
"""

from __future__ import annotations

import json
import os
from collections.abc import Sequence

from mergegate.acceptance.commands import COMMAND_NOT_FOUND_EXIT_CODE, run_command
from mergegate.harness.base import HarnessAdapter, HarnessError, HarnessResult
from mergegate.models.attempt import StructuredFeedback
from mergegate.workspace.worktree import Worktree, capture_diff

DEFAULT_EXECUTABLE = "cursor-agent"
DEFAULT_TIMEOUT_S = 600.0
API_KEY_ENV_VAR = "CURSOR_API_KEY"


def _as_argv(executable: str | Sequence[str]) -> list[str]:
    if isinstance(executable, str):
        return [executable]
    return list(executable)


def _build_prompt(objective: str, feedback: StructuredFeedback | None) -> str:
    """Compose the print-mode prompt, folding in the prior attempt's failure.

    Grounding the retry in the *specific* failing criterion/command/signature
    (rather than just "it failed") is what lets the harness make targeted
    progress instead of re-guessing from scratch each attempt.
    """
    if feedback is None:
        return objective

    return (
        f"{objective}\n\n"
        "The previous attempt failed acceptance. Fix this before anything else:\n"
        f"- Criterion: {feedback.criterion}\n"
        f"- Command: {feedback.command} (exit code {feedback.exit_code})\n"
        f"- Failure: {feedback.failure_signature}"
    )


def _parse_usage(stdout: str) -> tuple[int, int, float]:
    """Best-effort usage extraction from a trailing JSON line in stdout.

    `cursor-agent`'s JSON usage schema isn't a contract we control, so a line
    that isn't valid JSON (or has no `usage` object) just yields no usage
    data rather than failing the call — the diff was already captured from
    git and is real regardless of whether usage could be parsed.
    """
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        usage = payload.get("usage") if isinstance(payload, dict) else None
        if not isinstance(usage, dict):
            continue
        tokens = int(usage.get("tokens", 0) or 0)
        model_calls = int(usage.get("model_calls", 0) or 0)
        usd = float(usage.get("usd", 0.0) or 0.0)
        return tokens, model_calls, usd
    return 0, 0, 0.0


class CursorAdapter(HarnessAdapter):
    """Headless `cursor-agent` CLI adapter (research.md R5's default provider)."""

    def __init__(
        self,
        *,
        executable: str | Sequence[str] = DEFAULT_EXECUTABLE,
        api_key: str | None = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        self._executable = _as_argv(executable)
        self._api_key = api_key
        self._timeout_s = timeout_s

    def propose_changes(
        self,
        objective: str,
        feedback: StructuredFeedback | None,
        workspace: Worktree,
    ) -> HarnessResult:
        api_key = self._api_key or os.environ.get(API_KEY_ENV_VAR)
        if not api_key:
            raise HarnessError(
                f"{API_KEY_ENV_VAR} is not set; cannot invoke cursor-agent"
            )

        prompt = _build_prompt(objective, feedback)
        argv = [
            *self._executable,
            "-p",
            prompt,
            "--force",
            "--output-format",
            "json",
        ]

        result = run_command(
            argv,
            cwd=workspace.path,
            extra_env={API_KEY_ENV_VAR: api_key},
            timeout_s=self._timeout_s,
        )

        if result.exit_code == COMMAND_NOT_FOUND_EXIT_CODE:
            raise HarnessError(f"{self._executable[0]!r} executable not found on PATH")

        diff = capture_diff(workspace)
        tokens, model_calls, usd = _parse_usage(result.stdout)

        return HarnessResult(
            diff=diff.patch,
            changed_files=diff.changed_files,
            log=result.stdout + result.stderr,
            tokens=tokens,
            model_calls=model_calls,
            usd=usd,
        )
