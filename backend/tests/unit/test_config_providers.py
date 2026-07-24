"""US8 provider-selection tests (T065, FR-034/FR-035)."""

from __future__ import annotations

from mergegate.config.providers import ProviderSelection, resolve_agent_provider
from mergegate.config.settings import Settings
from mergegate.models import AgentRole, Node, NodeConfig, NodeType, Workflow


def _workflow_with_execution(config: NodeConfig | None = None) -> Workflow:
    return Workflow(
        id="provider-test",
        name="Provider test",
        version="1.0.0",
        nodes=[
            Node(id="input", type=NodeType.INPUT, name="Input"),
            Node(
                id="execution",
                type=NodeType.AGENT,
                name="Execution",
                config=config or NodeConfig(role=AgentRole.EXECUTION),
            ),
            Node(id="success", type=NodeType.SUCCESS, name="Success"),
            Node(id="stop", type=NodeType.STOP, name="Stop"),
        ],
        edges=[],
    )


def _settings(provider: str = "cursor", model: str = "auto") -> Settings:
    return Settings(
        provider=provider,
        model=model,
        max_attempts=3,
        max_wall_clock_s=300,
        max_model_calls=10,
    )


def test_resolves_provider_for_the_requested_agent_node() -> None:
    workflow = _workflow_with_execution(
        NodeConfig(
            role=AgentRole.EXECUTION,
            provider="gemini",
            model="gemini-2.5-flash",
        )
    )

    selection = resolve_agent_provider(
        workflow, AgentRole.EXECUTION, settings=_settings()
    )

    assert selection == ProviderSelection(
        provider="gemini",
        model="gemini-2.5-flash",
        node_id="execution",
    )


def test_external_config_can_swap_provider_without_editing_workflow() -> None:
    workflow = _workflow_with_execution()
    workflow_before = workflow.model_dump_json()

    first = resolve_agent_provider(
        workflow,
        AgentRole.EXECUTION,
        settings=_settings("aider", "sonnet"),
    )
    second = resolve_agent_provider(
        workflow,
        AgentRole.EXECUTION,
        settings=_settings("codex", "gpt-5.3-codex"),
    )

    assert first.provider == "aider"
    assert second.provider == "codex"
    assert workflow.model_dump_json() == workflow_before


def test_explicit_run_selection_overrides_node_and_process_defaults() -> None:
    workflow = _workflow_with_execution(
        NodeConfig(
            role=AgentRole.EXECUTION,
            provider="anthropic",
            model="claude-sonnet-4-5",
        )
    )

    selection = resolve_agent_provider(
        workflow,
        AgentRole.EXECUTION,
        settings=_settings(),
        provider="gemini",
        model="gemini-2.5-flash",
    )

    assert selection.provider == "gemini"
    assert selection.model == "gemini-2.5-flash"


def test_explicit_provider_does_not_inherit_another_providers_node_model() -> None:
    workflow = _workflow_with_execution(
        NodeConfig(
            role=AgentRole.EXECUTION,
            provider="anthropic",
            model="claude-sonnet-4-5",
        )
    )

    selection = resolve_agent_provider(
        workflow,
        AgentRole.EXECUTION,
        settings=_settings(model="auto"),
        provider="gemini",
    )

    assert selection == ProviderSelection(
        provider="gemini", model="auto", node_id="execution"
    )
