"""Verdict and CheckResult models — the deterministic acceptance output
(Principle I/II, FR-009, FR-010).
"""

from pydantic import BaseModel, Field

from mergegate.models.enums import CheckStep, PassFail


class CheckResult(BaseModel):
    """Outcome of one step in the ordered acceptance pipeline."""

    criterion_id: str
    step: CheckStep
    passed: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    baseline_result: PassFail | None = None


class Verdict(BaseModel):
    """Deterministic pass/fail for an attempt, computed only by the
    acceptance engine.
    """

    attempt_id: str
    passed: bool
    checks: list[CheckResult] = Field(default_factory=list)
    acceptance_hash: str
    acceptance_input: dict
    replay_of: str | None = None
