"""LLM-free deterministic acceptance engine (Constitution Principle I/II).

This package computes verdicts from files, commands, and exit codes only — it
never calls a model. `commands` provides the low-level primitive that every
acceptance check is built on: run a command and capture its stdout, stderr,
exit code, and duration deterministically.
"""

from mergegate.acceptance.commands import (
    COMMAND_NOT_FOUND_EXIT_CODE,
    DEFAULT_TIMEOUT_S,
    TIMEOUT_EXIT_CODE,
    CommandResult,
    run_command,
)
from mergegate.acceptance.verdict import (
    ACCEPTANCE_INPUT_KEYS,
    build_acceptance_input,
    compute_acceptance_hash,
    compute_verdict,
)

__all__ = [
    "ACCEPTANCE_INPUT_KEYS",
    "COMMAND_NOT_FOUND_EXIT_CODE",
    "DEFAULT_TIMEOUT_S",
    "TIMEOUT_EXIT_CODE",
    "CommandResult",
    "build_acceptance_input",
    "compute_acceptance_hash",
    "compute_verdict",
    "run_command",
]
