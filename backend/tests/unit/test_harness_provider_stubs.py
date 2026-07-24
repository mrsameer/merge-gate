"""US8 harness adapter coverage for Aider, Claude Agent SDK, and Codex."""

from __future__ import annotations

import pytest

from mergegate.harness.aider import AiderHarnessAdapter
from mergegate.harness.anthropic import AnthropicHarnessAdapter
from mergegate.harness.base import HarnessAdapter, HarnessError
from mergegate.harness.claude_agent_sdk import ClaudeAgentSDKHarnessAdapter
from mergegate.harness.codex import CodexHarnessAdapter
from mergegate.harness.registry import get_adapter


@pytest.mark.parametrize(
    ("provider", "adapter_type"),
    [
        ("aider", AiderHarnessAdapter),
        ("claude-agent-sdk", ClaudeAgentSDKHarnessAdapter),
        ("codex", CodexHarnessAdapter),
    ],
)
def test_registry_exposes_us8_provider_adapters(
    provider: str, adapter_type: type[HarnessAdapter]
) -> None:
    adapter = get_adapter(provider, model="configured-model")

    assert isinstance(adapter, adapter_type)
    assert isinstance(adapter, HarnessAdapter)


def test_claude_agent_sdk_reuses_the_existing_anthropic_adapter() -> None:
    assert issubclass(ClaudeAgentSDKHarnessAdapter, AnthropicHarnessAdapter)


@pytest.mark.parametrize(
    ("adapter", "provider_name"),
    [
        (AiderHarnessAdapter(model="sonnet"), "Aider"),
        (CodexHarnessAdapter(model="gpt-5.3-codex"), "Codex"),
    ],
)
def test_unwired_provider_stubs_fail_truthfully(
    adapter: HarnessAdapter, provider_name: str
) -> None:
    with pytest.raises(HarnessError, match=provider_name):
        adapter.propose_changes("objective", None, None)  # type: ignore[arg-type]
