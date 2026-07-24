"""Claude Agent SDK provider name backed by the existing Anthropic adapter."""

from mergegate.harness.anthropic import AnthropicHarnessAdapter


class ClaudeAgentSDKHarnessAdapter(AnthropicHarnessAdapter):
    """Compatibility adapter for the explicit ``claude-agent-sdk`` provider.

    The repository already has a complete Claude Agent SDK implementation
    under the ``anthropic`` provider name, so this adapter intentionally
    inherits it rather than duplicating credential, execution, and usage
    behavior.
    """
