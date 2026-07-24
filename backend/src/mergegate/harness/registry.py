"""T016b — Provider registry mapping a provider name to a `HarnessAdapter`
(FR-034, FR-035, research.md R5).

`config/settings.py` resolves *which* provider a run uses (a plain string);
this registry is the single place that turns that string into a concrete
adapter, so adding a provider is one entry here rather than a change scattered
across the orchestrator. An unknown name fails loudly with a `ValueError` that
lists the providers that do exist, never a silent fallback.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from mergegate.harness.anthropic import AnthropicHarnessAdapter
from mergegate.harness.base import HarnessAdapter
from mergegate.harness.cursor import CursorAdapter
from mergegate.harness.gemini import GeminiHarnessAdapter
from mergegate.harness.scripted import ScriptedHarnessAdapter

# Provider name -> adapter factory. Factories accept keyword args so callers
# can pass provider-specific configuration (model, api_key, changes, ...).
ADAPTER_FACTORIES: Mapping[str, Callable[..., HarnessAdapter]] = {
    "cursor": CursorAdapter,
    "gemini": GeminiHarnessAdapter,
    "anthropic": AnthropicHarnessAdapter,
    "scripted": ScriptedHarnessAdapter,
}


def get_adapter(provider: str, **kwargs: Any) -> HarnessAdapter:
    """Construct the `HarnessAdapter` registered under `provider`.

    Args:
        provider: The provider name (e.g. from `resolve_provider`).
        **kwargs: Forwarded to the selected adapter's constructor.

    Returns:
        A ready-to-use `HarnessAdapter`.

    Raises:
        ValueError: If `provider` is not a registered provider.
    """
    try:
        factory = ADAPTER_FACTORIES[provider]
    except KeyError:
        known = ", ".join(sorted(ADAPTER_FACTORIES))
        raise ValueError(
            f"unknown provider {provider!r}; known providers: {known}"
        ) from None

    return factory(**kwargs)
