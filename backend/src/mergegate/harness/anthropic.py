"""T016b — Anthropic Claude Agent SDK adapter implementing `HarnessAdapter`
(FR-034, FR-035, research.md R5).

SDK path taken: the official **Claude Agent SDK** for Python
(`claude-agent-sdk`, resolved and installed successfully in this environment),
so this adapter drives the same agent loop the Claude Code CLI uses rather than
hand-rolling a tool-use loop against the raw Messages API. The SDK's `query`
runs the agent non-interactively inside the attempt's worktree (`cwd`), letting
it edit files and run commands confined to that directory; as with
`cursor.py`, the diff it produced is recovered afterwards from git
(`capture_diff`) rather than parsed out of the agent's own transcript, and the
transcript text is kept only as the log.

Authentication is an `ANTHROPIC_API_KEY` (falling back to `CLAUDE_CODE_API_KEY`
when set) read from the environment — never hardcoded. A missing key, or the
SDK's CLI not being available, means the harness can't even be invoked, so the
adapter raises `HarnessError` up front rather than spawning a run doomed to
fail (Principle IV: a crash must never be recorded as a successful, if empty,
attempt). A run that completes but changes nothing is a legitimate
`HarnessResult` with an empty `diff`, not an error.

The SDK `query` callable is injectable so tests exercise the whole contract —
prompt construction, diff recovery, usage mapping, and the error paths — with a
fake async agent, needing no network and no real key; only live runs need a
real key.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Callable
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKError,
    PermissionMode,
    ResultMessage,
    TextBlock,
)
from claude_agent_sdk import query as sdk_query

from mergegate.harness.base import HarnessAdapter, HarnessError, HarnessResult
from mergegate.models.attempt import StructuredFeedback
from mergegate.workspace.worktree import Worktree, capture_diff

API_KEY_ENV_VAR = "ANTHROPIC_API_KEY"
FALLBACK_API_KEY_ENV_VAR = "CLAUDE_CODE_API_KEY"

# Fully autonomous: the agent may edit files and run commands without an
# interactive approval prompt. Confinement comes from running inside the
# attempt's isolated worktree (`cwd`), never a shared tree.
DEFAULT_PERMISSION_MODE: PermissionMode = "bypassPermissions"

# Token fields summed into `HarnessResult.tokens` from the SDK usage object.
_TOKEN_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
)

# The SDK `query` signature: called with keyword `prompt`/`options`, returns an
# async iterator of agent messages. Injectable so tests can supply a fake.
QueryFn = Callable[..., AsyncIterator[Any]]


def _build_prompt(objective: str, feedback: StructuredFeedback | None) -> str:
    """Compose the agent prompt, folding in the prior attempt's failure.

    Grounding the retry in the *specific* failing criterion/command/signature
    (rather than just "it failed") is what lets the agent make targeted
    progress instead of re-guessing from scratch each attempt (mirrors
    `cursor.py`).
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


def _extract_usage(message: ResultMessage) -> tuple[int, int, float]:
    """Map an SDK `ResultMessage` onto this call's `(tokens, model_calls, usd)`.

    The usage object's schema isn't a contract we control, so missing or
    non-numeric fields simply contribute nothing rather than failing the call —
    the diff was already captured from git and is real regardless of whether
    usage could be read.
    """
    usage = getattr(message, "usage", None)
    tokens = 0
    if isinstance(usage, dict):
        for key in _TOKEN_FIELDS:
            try:
                tokens += int(usage.get(key, 0) or 0)
            except (TypeError, ValueError):
                continue

    try:
        model_calls = int(getattr(message, "num_turns", 0) or 0)
    except (TypeError, ValueError):
        model_calls = 0
    try:
        usd = float(getattr(message, "total_cost_usd", 0.0) or 0.0)
    except (TypeError, ValueError):
        usd = 0.0

    return tokens, model_calls, usd


class AnthropicHarnessAdapter(HarnessAdapter):
    """Claude Agent SDK adapter (research.md R5's Anthropic provider)."""

    def __init__(
        self,
        *,
        model: str | None = None,
        api_key: str | None = None,
        permission_mode: PermissionMode = DEFAULT_PERMISSION_MODE,
        query_fn: QueryFn = sdk_query,
    ) -> None:
        self._model = model
        self._api_key = api_key
        self._permission_mode: PermissionMode = permission_mode
        self._query_fn = query_fn

    def propose_changes(
        self,
        objective: str,
        feedback: StructuredFeedback | None,
        workspace: Worktree,
    ) -> HarnessResult:
        api_key = (
            self._api_key
            or os.environ.get(API_KEY_ENV_VAR)
            or os.environ.get(FALLBACK_API_KEY_ENV_VAR)
        )
        if not api_key:
            raise HarnessError(
                f"{API_KEY_ENV_VAR} (or {FALLBACK_API_KEY_ENV_VAR}) is not set; "
                "cannot invoke the Claude Agent SDK"
            )

        prompt = _build_prompt(objective, feedback)
        options = ClaudeAgentOptions(
            cwd=str(workspace.path),
            permission_mode=self._permission_mode,
            model=self._model,
            env={API_KEY_ENV_VAR: api_key},
        )

        try:
            log, usage = asyncio.run(self._run_agent(prompt, options))
        except ClaudeSDKError as exc:
            raise HarnessError(f"Claude Agent SDK could not be invoked: {exc}") from exc

        diff = capture_diff(workspace)
        tokens, model_calls, usd = usage

        return HarnessResult(
            diff=diff.patch,
            changed_files=diff.changed_files,
            log=log,
            tokens=tokens,
            model_calls=model_calls,
            usd=usd,
        )

    async def _run_agent(
        self, prompt: str, options: ClaudeAgentOptions
    ) -> tuple[str, tuple[int, int, float]]:
        """Drive the agent to completion, collecting its transcript and usage.

        Assistant text blocks and the final result string form the log; usage
        is taken from the terminating `ResultMessage`. Tool-use blocks (the
        agent's file edits and commands) are intentionally not parsed — their
        effect is recovered from git afterwards.
        """
        log_parts: list[str] = []
        usage = (0, 0, 0.0)

        async for message in self._query_fn(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        log_parts.append(block.text)
            elif isinstance(message, ResultMessage):
                usage = _extract_usage(message)
                if message.result:
                    log_parts.append(message.result)

        return "\n".join(log_parts), usage
