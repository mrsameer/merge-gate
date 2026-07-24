"""Shared behavior for selectable provider adapters that are not wired yet."""

from __future__ import annotations

from mergegate.harness.base import HarnessAdapter, HarnessError, HarnessResult
from mergegate.models.attempt import StructuredFeedback
from mergegate.workspace.worktree import Worktree


class UnavailableHarnessAdapter(HarnessAdapter):
    """A truthful, fail-closed adapter placeholder.

    Registering a provider proves configuration/selection independently of
    installing its CLI.  Invocation fails explicitly so an unavailable
    provider can never be mistaken for a successful no-op run.
    """

    display_name = "Provider"

    def __init__(self, *, model: str | None = None) -> None:
        self.model = model

    def propose_changes(
        self,
        objective: str,
        feedback: StructuredFeedback | None,
        workspace: Worktree,
    ) -> HarnessResult:
        raise HarnessError(
            f"{self.display_name} provider is selectable but not wired; "
            "configure a provider with an installed coding harness"
        )
