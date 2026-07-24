from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class HarnessResult:
    diff: str
    changed_files: list[str]
    log: str
    tokens: int = 0
    model_calls: int = 1
    usd: float = 0.0


class HarnessAdapter(ABC):
    def prepare_acceptance_tests(
        self,
        *,
        objective: str,
        workspace: str,
    ) -> HarnessResult:
        """Add task-specific acceptance tests before baseline red-check."""
        return HarnessResult(
            diff="",
            changed_files=[],
            log="",
            tokens=0,
            model_calls=0,
            usd=0.0,
        )

    @abstractmethod
    def propose_changes(
        self,
        *,
        objective: str,
        feedback: dict[str, Any] | None,
        workspace: str,
    ) -> HarnessResult:
        raise NotImplementedError
