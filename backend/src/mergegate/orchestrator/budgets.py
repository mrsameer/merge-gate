from __future__ import annotations

from datetime import UTC, datetime

from mergegate.models import Run


def budget_exhausted(run: Run, *, started_at: datetime) -> str | None:
    if run.current_attempt >= run.budgets.max_attempts:
        return "max_attempts"
    elapsed = (datetime.now(tz=UTC) - started_at).total_seconds()
    if elapsed >= run.budgets.max_wall_clock_s:
        return "max_wall_clock_s"
    if run.cost.model_calls >= run.budgets.max_model_calls:
        return "max_model_calls"
    return None


def can_start_attempt(run: Run, *, started_at: datetime) -> bool:
    return budget_exhausted(run, started_at=started_at) is None
