"""Attempt and StructuredFeedback models — one iteration within a Run, bound
to an isolated workspace (FR-011, FR-012, FR-014).
"""

from pydantic import BaseModel, Field

from mergegate.models.verdict import Verdict


class StructuredFeedback(BaseModel):
    """Failure feedback fed into the next Planning attempt (FR-012)."""

    criterion: str
    command: str
    exit_code: int
    failure_signature: str
    first_failing_location: str | None = None
    attempt: int


class Attempt(BaseModel):
    """One iteration within a Run, bound to an isolated workspace."""

    id: str
    run_id: str
    index: int
    worktree_path: str
    branch: str
    diff: str
    changed_files: list[str] = Field(default_factory=list)
    harness_log: str
    verdict: Verdict | None = None
    red_green_evidence: dict | None = None
    failure_signature: str | None = None
    feedback: StructuredFeedback | None = None
