"""T015 — Provider adapter interface `HarnessAdapter` (FR-034, FR-035,
research.md R5).

The coding harness that actually edits files and runs commands sits behind
this one interface so the provider and model family are a configuration
choice, never a hardcoded dependency of the orchestrator (Principle I keeps
this physically separate from `acceptance/`, which decides pass/fail — the
harness only ever proposes a change).

A provider adapter implements a single method, `propose_changes`, which takes
the current objective, the previous attempt's structured feedback (`None` on
the first attempt), and the `Worktree` to work in, and returns a
`HarnessResult` — the diff it produced plus its log and usage. Returning a
result with an empty `diff` is a legitimate outcome (the harness ran but made
no change); `HarnessError` is reserved for the harness failing to run at all
(missing executable, invalid credentials), so the orchestrator can tell
"no progress" apart from "couldn't even try" (Principle IV — a crash must
never be recorded as a successful attempt).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from mergegate.models.attempt import StructuredFeedback
from mergegate.workspace.worktree import Worktree


class HarnessError(RuntimeError):
    """Raised when a provider adapter cannot invoke its coding harness at all.

    Distinct from the harness running and proposing no change, which is a
    legitimate `HarnessResult` with an empty `diff`.
    """


class HarnessTimeoutError(HarnessError):
    """Raised when a coding harness exceeds its configured wall-clock limit."""


@dataclass(frozen=True)
class HarnessResult:
    """Outcome of one `propose_changes` call (data-model.md § ProviderAdapter).

    `tokens`, `model_calls`, and `usd` are this call's usage only — the
    orchestrator accumulates them into the run's `CostAccounting`.
    """

    diff: str
    changed_files: list[str] = field(default_factory=list)
    log: str = ""
    tokens: int = 0
    model_calls: int = 0
    usd: float = 0.0


class HarnessAdapter(ABC):
    """Provider-agnostic interface to a coding harness (FR-034/FR-035).

    Selected via configuration (`config/settings.py`); the orchestrator calls
    `propose_changes` without knowing which provider is behind it, so
    swapping providers never touches the workflow definition.
    """

    @abstractmethod
    def propose_changes(
        self,
        objective: str,
        feedback: StructuredFeedback | None,
        workspace: Worktree,
    ) -> HarnessResult:
        """Drive the harness to propose a change for `objective` in `workspace`.

        Args:
            objective: The task the harness should attempt.
            feedback: The previous attempt's failure feedback, or `None` on
                the first attempt.
            workspace: The isolated `Worktree` the harness must confine its
                filesystem and shell access to.

        Returns:
            A `HarnessResult` describing what the harness produced, even if
            `diff` is empty.

        Raises:
            HarnessError: If the harness itself could not be invoked.
        """
        raise NotImplementedError
