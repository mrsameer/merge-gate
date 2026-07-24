"""Provider/model selection for configurable Agent nodes (US8, T065).

The workflow carries optional provider settings on each Agent node, while
process settings provide defaults and a run request may provide an explicit
one-off override.  This module is the single place that applies that
precedence, so the orchestration layer receives a resolved selection without
knowing where it came from.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from mergegate.models import AgentRole, NodeConfig, NodeType, Workflow

if TYPE_CHECKING:
    from mergegate.config.settings import Settings


@dataclass(frozen=True)
class ProviderSelection:
    """The provider/model resolved for one Agent node."""

    provider: str
    model: str
    node_id: str | None = None


def resolve_provider(
    settings: Settings, node_config: NodeConfig | None
) -> tuple[str, str]:
    """Layer an Agent node's optional selection over process defaults."""
    if node_config is None:
        return settings.provider, settings.model
    return (
        node_config.provider or settings.provider,
        node_config.model or settings.model,
    )


def resolve_agent_provider(
    workflow: Workflow,
    role: AgentRole,
    *,
    settings: Settings,
    provider: str | None = None,
    model: str | None = None,
) -> ProviderSelection:
    """Resolve provider/model for the Agent node with ``role``.

    Precedence is explicit run selection, then the matching node's config,
    then process settings.  Run overrides are configuration attached to a run,
    not graph mutations, so callers can demonstrate a provider swap while
    keeping the serialized workflow byte-for-byte unchanged.
    """
    node = next(
        (
            item
            for item in workflow.nodes
            if item.type == NodeType.AGENT
            and item.config is not None
            and item.config.role == role
        ),
        None,
    )
    node_config = node.config if node is not None else None
    resolved_provider, resolved_model = resolve_provider(settings, node_config)
    if provider is not None:
        resolved_provider = provider
        # A model attached to a different node-level provider is not a safe
        # default for an explicit provider swap.
        resolved_model = model or settings.model
    elif model is not None:
        resolved_model = model
    return ProviderSelection(
        provider=resolved_provider,
        model=resolved_model,
        node_id=node.id if node is not None else None,
    )
