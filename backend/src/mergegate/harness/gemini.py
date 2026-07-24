"""Gemini CLI harness adapter.

Gemini CLI is a coding agent with filesystem and shell tools. Running it in
headless mode inside MergeGate's disposable worktree keeps all proposed edits
isolated, while the separate acceptance engine remains the sole authority for
the verdict. The CLI supports either its saved Google OAuth session (created
by running ``gemini`` and choosing *Sign in with Google*) or ``GEMINI_API_KEY``;
this adapter intentionally does not handle OAuth tokens itself.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from mergegate.acceptance.commands import COMMAND_NOT_FOUND_EXIT_CODE, run_command
from mergegate.harness.base import HarnessAdapter, HarnessError, HarnessResult
from mergegate.models.attempt import StructuredFeedback
from mergegate.workspace.worktree import Worktree, capture_diff

DEFAULT_EXECUTABLE = "gemini"
DEFAULT_TIMEOUT_S = 600.0
GEMINI_API_KEY_ENV_VAR = "GEMINI_API_KEY"


def _as_argv(executable: str | Sequence[str]) -> list[str]:
    return [executable] if isinstance(executable, str) else list(executable)


def _build_prompt(objective: str, feedback: StructuredFeedback | None) -> str:
    if feedback is None:
        return objective
    return (
        f"{objective}\n\n"
        "The previous attempt failed acceptance. Fix this before anything else:\n"
        f"- Criterion: {feedback.criterion}\n"
        f"- Command: {feedback.command} (exit code {feedback.exit_code})\n"
        f"- Failure: {feedback.failure_signature}"
    )


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _parse_usage(stdout: str) -> tuple[int, int]:
    """Read Gemini CLI's JSON metrics without trusting output for edits.

    Current CLI JSON output exposes ``stats.models.<model>.tokens.total`` and
    ``api.totalRequests``. The fallback input/output sum makes this resilient
    to older CLI releases while keeping usage accounting best-effort.
    """
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return 0, 0
    if not isinstance(payload, dict):
        return 0, 0
    stats = payload.get("stats")
    models = stats.get("models") if isinstance(stats, dict) else None
    if not isinstance(models, dict):
        return 0, 0

    tokens = 0
    model_calls = 0
    for metrics in models.values():
        if not isinstance(metrics, dict):
            continue
        token_metrics = metrics.get("tokens")
        if isinstance(token_metrics, dict):
            total = _as_int(token_metrics.get("total"))
            tokens += total or (
                _as_int(token_metrics.get("input"))
                + _as_int(token_metrics.get("output"))
            )
        api_metrics = metrics.get("api")
        if isinstance(api_metrics, dict):
            model_calls += _as_int(
                api_metrics.get("totalRequests", api_metrics.get("requests"))
            )
    return tokens, model_calls


class GeminiHarnessAdapter(HarnessAdapter):
    """Headless Gemini CLI adapter, authenticated by OAuth session or API key."""

    def __init__(
        self,
        *,
        executable: str | Sequence[str] = DEFAULT_EXECUTABLE,
        model: str | None = None,
        api_key: str | None = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        self._executable = _as_argv(executable)
        self._model = model
        self._api_key = api_key
        self._timeout_s = timeout_s

    def propose_changes(
        self,
        objective: str,
        feedback: StructuredFeedback | None,
        workspace: Worktree,
    ) -> HarnessResult:
        argv = [*self._executable, "-p", _build_prompt(objective, feedback)]
        if self._model:
            argv.extend(["-m", self._model])
        argv.extend(["--output-format", "json", "--yolo", "--skip-trust"])

        extra_env = {GEMINI_API_KEY_ENV_VAR: self._api_key} if self._api_key else None
        result = run_command(
            argv,
            cwd=workspace.path,
            extra_env=extra_env,
            timeout_s=self._timeout_s,
        )
        if result.exit_code == COMMAND_NOT_FOUND_EXIT_CODE:
            raise HarnessError(f"{self._executable[0]!r} executable not found on PATH")
        if not result.succeeded:
            detail = (result.stderr or result.stdout).strip()
            suffix = f": {detail}" if detail else ""
            raise HarnessError(f"Gemini CLI exited with {result.exit_code}{suffix}")

        diff = capture_diff(workspace)
        tokens, model_calls = _parse_usage(result.stdout)
        return HarnessResult(
            diff=diff.patch,
            changed_files=diff.changed_files,
            log=result.stdout + result.stderr,
            tokens=tokens,
            model_calls=model_calls,
            # OAuth-backed CLI usage does not report per-call monetary cost.
            usd=0.0,
        )
