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
    @abstractmethod
    def propose_changes(
        self,
        *,
        objective: str,
        feedback: dict[str, Any] | None,
        workspace: str,
    ) -> HarnessResult:
        raise NotImplementedError
