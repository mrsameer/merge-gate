"""Run model — a single execution of a workflow against an objective."""

from datetime import datetime

from pydantic import BaseModel, Field

from mergegate.models.attempt import Attempt
from mergegate.models.budget import Budget, CostAccounting
from mergegate.models.enums import RunStatus
from mergegate.models.policy import Policy


class ClarificationRequest(BaseModel):
    """Structured operator decision required before a run may execute."""

    reason: str
    conflicting_criteria: list[str] = Field(min_length=1)


class Run(BaseModel):
    """A single execution of a workflow against an objective."""

    id: str
    workflow_id: str
    objective: str
    repo_ref: str
    provider: str | None = None
    model: str | None = None
    location: str = "global"
    policy: Policy = Field(default_factory=Policy)
    status: RunStatus
    budgets: Budget
    attempts: list[Attempt] = Field(default_factory=list)
    current_attempt: int
    cost: CostAccounting
    started_at: datetime | None = None
    ended_at: datetime | None = None
    branch: str | None = None
    patch_ref: str | None = None
    undelivered_report: dict | None = None
    clarification: ClarificationRequest | None = None
