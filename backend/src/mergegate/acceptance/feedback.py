"""Structured, deterministic feedback for the planning retry (US3/T038)."""

from __future__ import annotations

import re

from mergegate.models import CheckResult, StructuredFeedback
from mergegate.orchestrator.no_progress import failure_signature

_LOCATION = re.compile(r"(?P<path>[\w./-]+\.[\w]+):(?P<line>\d+)(?::\d+)?")


def _first_location(check: CheckResult) -> str | None:
    """Extract the first conventional ``path:line`` from check output."""
    match = _LOCATION.search(f"{check.stderr}\n{check.stdout}")
    return match.group(0) if match else None


def build_failure_feedback(
    checks: list[CheckResult],
    *,
    commands: dict[str, str],
    attempt: int,
) -> StructuredFeedback:
    """Build the planning input from the first deterministic failed check.

    The acceptance engine owns the check results; this helper merely retains
    the actionable facts that a retry needs. It deliberately has no model or
    harness dependency, preserving the acceptance/generation boundary.
    """
    failed = next((check for check in checks if not check.passed), None)
    if failed is None:
        return StructuredFeedback(
            criterion="",
            command="",
            exit_code=1,
            failure_signature="no failing check recorded",
            attempt=attempt,
        )

    return StructuredFeedback(
        criterion=failed.criterion_id,
        command=commands.get(failed.criterion_id, failed.criterion_id),
        exit_code=failed.exit_code,
        failure_signature=failure_signature(failed),
        first_failing_location=_first_location(failed),
        attempt=attempt,
    )
