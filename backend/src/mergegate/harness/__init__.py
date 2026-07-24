"""Provider adapter interface + coding harness implementations (Principle I).

The harness only ever proposes changes; acceptance (`mergegate.acceptance`)
is the separate, LLM-free module that decides pass/fail.
"""

from mergegate.harness.base import HarnessAdapter, HarnessError, HarnessResult

__all__ = [
    "HarnessAdapter",
    "HarnessError",
    "HarnessResult",
]
