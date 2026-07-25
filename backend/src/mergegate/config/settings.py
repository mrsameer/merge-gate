"""T017 — Settings/budgets/provider selection (env + workflow-driven)
(FR-013, FR-022, FR-034, FR-035, research.md R5).

Every run needs a default provider/model and a default attempt/time/model-call
budget before any workflow is loaded (FR-013, FR-034); `Settings` supplies
those from environment variables so they are configuration, never hardcoded.
A workflow may then carry its own `WorkflowBudgets` and per-node
`NodeConfig.provider`/`model`, which `resolve_budget`/`resolve_provider` layer
on top of the env defaults — only the fields the workflow actually sets are
overridden, everything else falls back to `Settings` (FR-035: substituting a
provider never requires changing the workflow definition).
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from pydantic import BaseModel

from mergegate.models.budget import Budget
from mergegate.models.workflow import NodeConfig, WorkflowBudgets

DEFAULT_PROVIDER = "cursor"
DEFAULT_MODEL = "auto"
DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_MAX_WALL_CLOCK_S = 1800
# A single real coding-agent attempt spends ~30 model turns; the scripted
# demo provider spends ~1. Keep the default high enough that live providers
# complete an attempt instead of tripping the budget on turn 20.
DEFAULT_MAX_MODEL_CALLS = 120

PROVIDER_ENV_VAR = "MERGEGATE_PROVIDER"
MODEL_ENV_VAR = "MERGEGATE_MODEL"
MAX_ATTEMPTS_ENV_VAR = "MERGEGATE_MAX_ATTEMPTS"
MAX_WALL_CLOCK_S_ENV_VAR = "MERGEGATE_MAX_WALL_CLOCK_S"
MAX_MODEL_CALLS_ENV_VAR = "MERGEGATE_MAX_MODEL_CALLS"
CORS_ALLOW_ORIGINS_ENV_VAR = "CORS_ALLOW_ORIGINS"


class Settings(BaseModel):
    """Process-wide provider and budget defaults (FR-013, FR-034)."""

    provider: str = DEFAULT_PROVIDER
    model: str = DEFAULT_MODEL
    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    max_wall_clock_s: int = DEFAULT_MAX_WALL_CLOCK_S
    max_model_calls: int = DEFAULT_MAX_MODEL_CALLS


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """Read `Settings` from `env` (`os.environ` if not given)."""
    if env is None:
        env = os.environ

    return Settings(
        provider=env.get(PROVIDER_ENV_VAR, DEFAULT_PROVIDER),
        model=env.get(MODEL_ENV_VAR, DEFAULT_MODEL),
        max_attempts=int(env.get(MAX_ATTEMPTS_ENV_VAR, DEFAULT_MAX_ATTEMPTS)),
        max_wall_clock_s=int(
            env.get(MAX_WALL_CLOCK_S_ENV_VAR, DEFAULT_MAX_WALL_CLOCK_S)
        ),
        max_model_calls=int(env.get(MAX_MODEL_CALLS_ENV_VAR, DEFAULT_MAX_MODEL_CALLS)),
    )


def load_cors_allow_origins(env: Mapping[str, str] | None = None) -> list[str]:
    """Return the explicit, comma-separated browser origins allowed by the API."""
    if env is None:
        env = os.environ
    return [
        origin.strip()
        for origin in env.get(CORS_ALLOW_ORIGINS_ENV_VAR, "").split(",")
        if origin.strip()
    ]


def resolve_budget(
    settings: Settings, workflow_budgets: WorkflowBudgets | None
) -> Budget:
    """Layer a workflow's optional budget override over the env defaults."""
    if workflow_budgets is None:
        return Budget(
            max_attempts=settings.max_attempts,
            max_wall_clock_s=settings.max_wall_clock_s,
            max_model_calls=settings.max_model_calls,
        )

    return Budget(
        max_attempts=workflow_budgets.max_attempts or settings.max_attempts,
        max_wall_clock_s=workflow_budgets.max_wall_clock_s or settings.max_wall_clock_s,
        max_model_calls=workflow_budgets.max_model_calls or settings.max_model_calls,
    )


def resolve_provider(
    settings: Settings, node_config: NodeConfig | None
) -> tuple[str, str]:
    """Backward-compatible entrypoint for provider selection."""
    from mergegate.config.providers import resolve_provider as _resolve_provider

    return _resolve_provider(settings, node_config)
