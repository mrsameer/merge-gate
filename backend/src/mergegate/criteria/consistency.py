"""Deterministic pre-execution consistency checks for acceptance contracts.

The detector is intentionally LLM-free: it recognizes explicit contradictory
or unresolved response requirements in criterion text, and structural
conflicts where the same command or request scope requires mutually exclusive
outcomes.  It returns one stable issue at a time so the orchestrator can halt
before creating an attempt (FR-016).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from mergegate.models import Contract, Criterion

_BOTH_STATUS_CODES = re.compile(
    r"\bboth\s+(?:http\s+)?([1-5]\d{2})\s+and\s+(?:http\s+)?([1-5]\d{2})\b",
    re.IGNORECASE,
)
_EITHER_STATUS_CODES = re.compile(
    r"\beither\s+(?:http\s+)?([1-5]\d{2})\s+or\s+(?:http\s+)?([1-5]\d{2})\b",
    re.IGNORECASE,
)
_UNRESOLVED_LANGUAGE = re.compile(
    r"\b(?:tbd|to be decided|not yet specified|unspecified|unclear)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ConsistencyIssue:
    """A conflict that requires an operator decision before execution."""

    reason: str
    conflicting_criteria: tuple[str, ...]


def detect_inconsistency(contract: Contract) -> ConsistencyIssue | None:
    """Return the first deterministic contradiction/ambiguity in ``contract``.

    Checks run in contract priority order and use only frozen criterion data.
    This keeps the result replayable and avoids asking a model to decide
    whether its own contract is executable.
    """

    criteria = sorted(contract.criteria, key=lambda item: (item.priority, item.id))

    textual = _detect_textual_issue(criteria)
    if textual is not None:
        return textual

    command_conflict = _detect_command_conflict(criteria)
    if command_conflict is not None:
        return command_conflict

    return _detect_scoped_status_conflict(criteria)


def _detect_textual_issue(criteria: list[Criterion]) -> ConsistencyIssue | None:
    for criterion in criteria:
        text = " ".join(
            part
            for part in (
                criterion.description,
                _string_params(criterion),
            )
            if part
        )
        both = _BOTH_STATUS_CODES.search(text)
        if both is not None and both.group(1) != both.group(2):
            first, second = both.groups()
            return ConsistencyIssue(
                reason=(
                    f"Criterion {criterion.id!r} requires the same outcome to "
                    f"return both HTTP {first} and HTTP {second}; choose one "
                    "status for that request."
                ),
                conflicting_criteria=(criterion.id,),
            )

        either = _EITHER_STATUS_CODES.search(text)
        if either is not None and either.group(1) != either.group(2):
            first, second = either.groups()
            return ConsistencyIssue(
                reason=(
                    f"Criterion {criterion.id!r} leaves the response status "
                    f"ambiguous between HTTP {first} and HTTP {second}; "
                    "specify the required status."
                ),
                conflicting_criteria=(criterion.id,),
            )

        unresolved = _UNRESOLVED_LANGUAGE.search(text)
        if unresolved is not None:
            return ConsistencyIssue(
                reason=(
                    f"Criterion {criterion.id!r} contains unresolved language "
                    f"({unresolved.group(0)!r}); replace it with a measurable "
                    "outcome."
                ),
                conflicting_criteria=(criterion.id,),
            )
    return None


def _detect_command_conflict(
    criteria: list[Criterion],
) -> ConsistencyIssue | None:
    by_command: dict[str, Criterion] = {}
    for criterion in criteria:
        if criterion.command is None or criterion.expected_exit_code is None:
            continue
        command = criterion.command.strip()
        if not command:
            continue
        previous = by_command.get(command)
        if previous is None:
            by_command[command] = criterion
            continue
        if previous.expected_exit_code != criterion.expected_exit_code:
            return ConsistencyIssue(
                reason=(
                    f"Criteria {previous.id!r} and {criterion.id!r} require "
                    f"the same command to exit with both "
                    f"{previous.expected_exit_code} and "
                    f"{criterion.expected_exit_code}; choose one expected "
                    "exit code."
                ),
                conflicting_criteria=(previous.id, criterion.id),
            )
    return None


def _detect_scoped_status_conflict(
    criteria: list[Criterion],
) -> ConsistencyIssue | None:
    by_scope: dict[tuple[str, ...], tuple[Criterion, int]] = {}
    for criterion in criteria:
        params = criterion.params or {}
        status_code = params.get("status_code")
        if not isinstance(status_code, int):
            continue
        scope = _request_scope(params)
        if scope is None:
            continue
        previous = by_scope.get(scope)
        if previous is None:
            by_scope[scope] = (criterion, status_code)
            continue
        previous_criterion, previous_status = previous
        if previous_status != status_code:
            return ConsistencyIssue(
                reason=(
                    f"Criteria {previous_criterion.id!r} and {criterion.id!r} "
                    f"require the same request scope to return both HTTP "
                    f"{previous_status} and HTTP {status_code}; choose one "
                    "status."
                ),
                conflicting_criteria=(previous_criterion.id, criterion.id),
            )
    return None


def _request_scope(params: dict) -> tuple[str, ...] | None:
    """Build an explicit request scope; avoid guessing from prose alone."""

    route = params.get("route")
    condition = params.get("condition") or params.get("request")
    if not isinstance(route, str) or not isinstance(condition, str):
        return None
    method = params.get("method", "")
    return (str(method).upper(), route, condition.casefold().strip())


def _string_params(criterion: Criterion) -> str:
    params = criterion.params or {}
    return " ".join(str(value) for value in params.values() if isinstance(value, str))
