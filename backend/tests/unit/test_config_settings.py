"""Unit tests for T017 — settings/budgets/provider selection (FR-013,
FR-022, FR-034, FR-035).

`Settings` supplies process-wide provider and budget defaults sourced from
environment variables. `resolve_budget`/`resolve_provider` layer a workflow's
optional overrides (`WorkflowBudgets`, `NodeConfig.provider`/`model`) on top
of those defaults, so a run without any workflow-level override still gets a
sane budget/provider and one that does override only shadows the fields it
sets.
"""

from __future__ import annotations

from mergegate.config.settings import (
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_MAX_MODEL_CALLS,
    DEFAULT_MAX_WALL_CLOCK_S,
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
    MAX_ATTEMPTS_ENV_VAR,
    MAX_MODEL_CALLS_ENV_VAR,
    MAX_WALL_CLOCK_S_ENV_VAR,
    MODEL_ENV_VAR,
    PROVIDER_ENV_VAR,
    Settings,
    load_settings,
    resolve_budget,
    resolve_provider,
)
from mergegate.models.budget import Budget
from mergegate.models.workflow import NodeConfig, WorkflowBudgets


def test_load_settings_defaults_when_env_empty() -> None:
    settings = load_settings({})

    assert settings == Settings(
        provider=DEFAULT_PROVIDER,
        model=DEFAULT_MODEL,
        max_attempts=DEFAULT_MAX_ATTEMPTS,
        max_wall_clock_s=DEFAULT_MAX_WALL_CLOCK_S,
        max_model_calls=DEFAULT_MAX_MODEL_CALLS,
    )


def test_load_settings_reads_overrides_from_env() -> None:
    settings = load_settings(
        {
            PROVIDER_ENV_VAR: "claude-agent-sdk",
            MODEL_ENV_VAR: "claude-opus-4-8",
            MAX_ATTEMPTS_ENV_VAR: "3",
            MAX_WALL_CLOCK_S_ENV_VAR: "900",
            MAX_MODEL_CALLS_ENV_VAR: "10",
        }
    )

    assert settings.provider == "claude-agent-sdk"
    assert settings.model == "claude-opus-4-8"
    assert settings.max_attempts == 3
    assert settings.max_wall_clock_s == 900
    assert settings.max_model_calls == 10


def test_load_settings_ignores_unrelated_env_vars() -> None:
    settings = load_settings({"PATH": "/usr/bin", "HOME": "/home/x"})

    assert settings.provider == DEFAULT_PROVIDER
    assert settings.max_attempts == DEFAULT_MAX_ATTEMPTS


def test_resolve_budget_without_workflow_override_uses_settings() -> None:
    settings = Settings(
        provider=DEFAULT_PROVIDER,
        model=DEFAULT_MODEL,
        max_attempts=5,
        max_wall_clock_s=1800,
        max_model_calls=20,
    )

    assert resolve_budget(settings, None) == Budget(
        max_attempts=5, max_wall_clock_s=1800, max_model_calls=20
    )


def test_resolve_budget_layers_partial_workflow_override() -> None:
    settings = Settings(
        provider=DEFAULT_PROVIDER,
        model=DEFAULT_MODEL,
        max_attempts=5,
        max_wall_clock_s=1800,
        max_model_calls=20,
    )
    workflow_budgets = WorkflowBudgets(max_attempts=2)

    budget = resolve_budget(settings, workflow_budgets)

    assert budget == Budget(max_attempts=2, max_wall_clock_s=1800, max_model_calls=20)


def test_resolve_provider_without_node_config_uses_settings() -> None:
    settings = Settings(
        provider="cursor",
        model="auto",
        max_attempts=DEFAULT_MAX_ATTEMPTS,
        max_wall_clock_s=DEFAULT_MAX_WALL_CLOCK_S,
        max_model_calls=DEFAULT_MAX_MODEL_CALLS,
    )

    assert resolve_provider(settings, None) == ("cursor", "auto")


def test_resolve_provider_layers_partial_node_override() -> None:
    settings = Settings(
        provider="cursor",
        model="auto",
        max_attempts=DEFAULT_MAX_ATTEMPTS,
        max_wall_clock_s=DEFAULT_MAX_WALL_CLOCK_S,
        max_model_calls=DEFAULT_MAX_MODEL_CALLS,
    )
    node_config = NodeConfig(model="claude-opus-4-8")

    assert resolve_provider(settings, node_config) == ("cursor", "claude-opus-4-8")
