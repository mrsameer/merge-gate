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
from mergegate.acceptance.engine import (
    PIPELINE_ORDER,
    AcceptanceEngine,
    default_engine,
    run_acceptance_pipeline,
)
from mergegate.acceptance.evaluators import (
    EVALUATOR_REGISTRY,
    Evaluator,
    register_evaluator,
)
from mergegate.acceptance.policy import check_policy

__all__ = [
    "COMMAND_NOT_FOUND_EXIT_CODE",
    "DEFAULT_TIMEOUT_S",
    "EVALUATOR_REGISTRY",
    "PIPELINE_ORDER",
    "TIMEOUT_EXIT_CODE",
    "AcceptanceEngine",
    "CommandResult",
    "Evaluator",
    "default_engine",
    "check_policy",
    "register_evaluator",
    "run_acceptance_pipeline",
    "run_command",
]
