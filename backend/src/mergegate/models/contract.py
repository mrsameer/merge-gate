"""Contract and Criterion models — frozen, human-approved acceptance criteria
(FR-001a/FR-001b/FR-002/FR-003).
"""

from pydantic import BaseModel, Field

from mergegate.models.enums import CheckStep, ContractMode, CriterionType, PassFail


class Criterion(BaseModel):
    """A single acceptance criterion (FR-001c)."""

    id: str
    type: CriterionType
    priority: int
    command: str | None = None
    expected_exit_code: int | None = None
    baseline_expected: PassFail | None = None
    result_expected: PassFail | None = None
    metric_path: str | None = None
    minimum: float | None = None
    params: dict | None = None
    step: CheckStep | None = None
    """Which ordered acceptance-pipeline step this criterion belongs to
    (research R2/T025). ``None`` means the criterion is evaluated outside the
    engine's ordered pipeline (e.g. anti-cheat policy criteria, handled by
    `acceptance/policy.py` in US5)."""


class Contract(BaseModel):
    """Frozen, human-approved criteria set for a Run."""

    id: str
    run_id: str
    mode: ContractMode = ContractMode.HYBRID
    criteria: list[Criterion] = Field(default_factory=list)
    approved: bool = False
    frozen_hash: str | None = None
