"""Run model — a single execution of a workflow against an objective."""

from datetime import datetime

from pydantic import BaseModel, Field

from mergegate.models.attempt import Attempt
from mergegate.models.budget import Budget, CostAccounting
from mergegate.models.enums import RunStatus


class Run(BaseModel):
    """A single execution of a workflow against an objective."""

    id: str
    workflow_id: str
    objective: str
    repo_ref: str
    provider: str | None = None
    model: str | None = None
    status: RunStatus
    budgets: Budget
    attempts: list[Attempt] = Field(default_factory=list)
    current_attempt: int
    cost: CostAccounting
    started_at: datetime | None = None
    ended_at: datetime | None = None
    branch: str | None = None
    patch_ref: str | None = None
