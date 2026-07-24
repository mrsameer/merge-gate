"""Budget and cost-accounting models (FR-013, FR-022)."""

from pydantic import BaseModel


class Budget(BaseModel):
    """Configurable ceilings a Run must stop at (FR-013)."""

    max_attempts: int
    max_wall_clock_s: int
    max_model_calls: int


class CostAccounting(BaseModel):
    """Accumulated model usage, spend, and wall-clock for a Run (FR-022).

    ``wall_clock_s`` accumulates the harness's execution wall-clock across
    attempts, alongside the token / model-call / USD usage the harness reports.
    """

    tokens: int = 0
    model_calls: int = 0
    usd: float = 0.0
    wall_clock_s: float = 0.0
