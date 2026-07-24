"""Run-level attempt, wall-clock, and model-call budget policy (US3/T040)."""

from __future__ import annotations

import time
from collections.abc import Callable

from mergegate.models import RunStatus


class BudgetGuard:
    """Evaluate every bounded-autonomy limit before work can continue."""

    def __init__(
        self,
        *,
        max_attempts: int,
        max_wall_clock_s: float,
        max_model_calls: int,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_attempts = max_attempts
        self.max_wall_clock_s = max_wall_clock_s
        self.max_model_calls = max_model_calls
        self._now = now
        self._started_at: float | None = None

    def start(self) -> None:
        self._started_at = self._now()

    def terminal_status(self, *, attempts: int, model_calls: int) -> RunStatus | None:
        """Return a safe terminal state when a new attempt must not begin."""
        if self._started_at is None:
            raise RuntimeError("budget guard must be started before evaluation")
        if self.max_wall_clock_s <= 0 or (
            self._now() - self._started_at >= self.max_wall_clock_s
        ):
            return RunStatus.TIMED_OUT
        if attempts >= self.max_attempts or model_calls >= self.max_model_calls:
            return RunStatus.EXHAUSTED
        return None


def budget_reason(
    status: RunStatus,
    *,
    attempts: int,
    model_calls: int,
    max_attempts: int,
    max_model_calls: int,
) -> str:
    """Human-readable terminal reason carried into the undelivered report."""
    if status == RunStatus.TIMED_OUT:
        return "wall-clock budget exhausted"
    if model_calls >= max_model_calls:
        return "model-call budget exhausted"
    if attempts >= max_attempts:
        return "attempt budget exhausted"
    return "budget exhausted"
