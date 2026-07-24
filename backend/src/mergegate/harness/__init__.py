"""Provider adapter interface + coding harness implementations (Principle I).

The harness only ever proposes changes; acceptance (`mergegate.acceptance`)
is the separate, LLM-free module that decides pass/fail.
"""

from mergegate.harness.aider import AiderHarnessAdapter
from mergegate.harness.base import HarnessAdapter, HarnessError, HarnessResult
from mergegate.harness.claude_agent_sdk import ClaudeAgentSDKHarnessAdapter
from mergegate.harness.codex import CodexHarnessAdapter
from mergegate.harness.cursor import CursorAdapter
from mergegate.harness.gemini import GeminiHarnessAdapter

__all__ = [
    "AiderHarnessAdapter",
    "ClaudeAgentSDKHarnessAdapter",
    "CodexHarnessAdapter",
    "CursorAdapter",
    "GeminiHarnessAdapter",
    "HarnessAdapter",
    "HarnessError",
    "HarnessResult",
]
