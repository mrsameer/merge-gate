"""Provider adapter interface + coding harness implementations (Principle I).

The harness only ever proposes changes; acceptance (`mergegate.acceptance`)
is the separate, LLM-free module that decides pass/fail.
"""

from mergegate.harness.base import HarnessAdapter, HarnessError, HarnessResult
from mergegate.harness.cursor import CursorAdapter
from mergegate.harness.gemini import GeminiHarnessAdapter

__all__ = [
    "CursorAdapter",
    "GeminiHarnessAdapter",
    "HarnessAdapter",
    "HarnessError",
    "HarnessResult",
]
