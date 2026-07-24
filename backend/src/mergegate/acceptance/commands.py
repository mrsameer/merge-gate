"""T024 — Deterministic command runner for the acceptance engine.

Every acceptance check ultimately reduces to running a command and observing
what happened: what it printed, whether it succeeded, and how long it took.
This module is that single primitive. It is intentionally the *only* place the
acceptance engine shells out, so capture is uniform and the recorded evidence
(stdout, stderr, exit code, duration) is consistent across every check
(FR-007, research R2).

Design choices that keep the runner deterministic and safe:

* **No shell.** Commands are executed as an argv list via `subprocess` without
  `shell=True`, avoiding shell-injection and shell-dependent word splitting. A
  string command is tokenized with `shlex` for convenience, but argv is
  preferred.
* **Always returns, never leaks.** A missing executable or a timeout is turned
  into a `CommandResult` with a well-defined exit code rather than an
  exception, so a check can be recorded as *failed* instead of crashing the run
  (Principle IV — an exception must never masquerade as success; it becomes a
  captured failure the engine can classify).
* **Bounded.** Every command has a wall-clock timeout; on expiry the process is
  killed, partial output is captured, and `timed_out` is set.
* **Stable text.** Output is decoded as UTF-8 with `errors="replace"` so binary
  noise can never raise mid-capture and identical bytes always decode to
  identical strings.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

# Default per-command wall-clock budget. Individual callers (the worktree
# command layer, T014) may pass a tighter or looser value.
DEFAULT_TIMEOUT_S: float = 120.0

# Exit code recorded when a command exceeds its timeout. 124 matches the GNU
# `timeout` utility so the value is recognizable in evidence; `timed_out` is the
# authoritative signal regardless of this number.
TIMEOUT_EXIT_CODE: int = 124

# Exit code recorded when the executable cannot be found. 127 is the POSIX
# shell convention for "command not found".
COMMAND_NOT_FOUND_EXIT_CODE: int = 127


@dataclass(frozen=True)
class CommandResult:
    """Immutable record of a single command execution.

    These four captured fields — ``exit_code``, ``stdout``, ``stderr``, and
    ``duration_ms`` — map directly onto ``CheckResult`` in the domain model, so
    a check step is just a ``CommandResult`` plus a criterion/step label.
    """

    command: tuple[str, ...]
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool = False
    cwd: str | None = None

    @property
    def succeeded(self) -> bool:
        """True only on a clean exit — zero status and no timeout."""
        return self.exit_code == 0 and not self.timed_out


def _normalize_command(command: Sequence[str] | str) -> list[str]:
    """Return an argv list, tokenizing a string command with POSIX rules."""
    if isinstance(command, str):
        argv = shlex.split(command)
    else:
        argv = [str(part) for part in command]

    if not argv:
        raise ValueError("command must contain at least one argument")
    return argv


def _build_env(
    env: Mapping[str, str] | None,
    extra_env: Mapping[str, str] | None,
) -> dict[str, str]:
    """Compose the child environment.

    Starts from the current process environment (or ``env`` when given as a
    full replacement), overlays ``extra_env``, and pins ``PYTHONIOENCODING`` so
    child Python processes emit UTF-8 regardless of the host locale — a small
    but important determinism guarantee.
    """
    base: dict[str, str] = dict(os.environ if env is None else env)
    if extra_env:
        base.update(extra_env)
    base.setdefault("PYTHONIOENCODING", "utf-8")
    return base


def run_command(
    command: Sequence[str] | str,
    *,
    cwd: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
    extra_env: Mapping[str, str] | None = None,
    timeout_s: float | None = DEFAULT_TIMEOUT_S,
) -> CommandResult:
    """Run ``command`` and capture stdout, stderr, exit code, and duration.

    Args:
        command: Argv sequence (preferred) or a string tokenized with ``shlex``.
        cwd: Working directory to run in — typically the attempt's git worktree.
        env: Full environment replacement; defaults to the current environment.
        extra_env: Extra variables overlaid on top of ``env``.
        timeout_s: Per-command wall-clock budget; ``None`` disables the timeout.

    Returns:
        A :class:`CommandResult`. Missing executables yield
        ``COMMAND_NOT_FOUND_EXIT_CODE`` and timeouts yield
        ``TIMEOUT_EXIT_CODE`` with ``timed_out=True`` — this function does not
        raise for those cases, so the caller can record them as failed checks.

    Raises:
        ValueError: If ``command`` is empty.
    """
    argv = _normalize_command(command)
    run_env = _build_env(env, extra_env)
    cwd_str = os.fspath(cwd) if cwd is not None else None

    started = time.monotonic()
    try:
        process = subprocess.Popen(
            argv,
            cwd=cwd_str,
            env=run_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        return CommandResult(
            command=tuple(argv),
            exit_code=COMMAND_NOT_FOUND_EXIT_CODE,
            stdout="",
            stderr=str(exc),
            duration_ms=duration_ms,
            timed_out=False,
            cwd=cwd_str,
        )

    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=timeout_s)
        exit_code = process.returncode
    except subprocess.TimeoutExpired:
        process.kill()
        # Drain whatever the killed process had already written.
        stdout, stderr = process.communicate()
        timed_out = True
        exit_code = TIMEOUT_EXIT_CODE

    duration_ms = int((time.monotonic() - started) * 1000)
    return CommandResult(
        command=tuple(argv),
        exit_code=exit_code,
        stdout=stdout or "",
        stderr=stderr or "",
        duration_ms=duration_ms,
        timed_out=timed_out,
        cwd=cwd_str,
    )
