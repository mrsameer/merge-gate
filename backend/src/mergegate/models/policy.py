"""Anti-cheat policy configuration and deterministic result models."""

from typing import Literal

from pydantic import BaseModel, Field


class Policy(BaseModel):
    """Protected paths and forbidden diff patterns enforced pre-acceptance."""

    protected_paths: list[str] = Field(default_factory=list)
    forbidden_diff_patterns: list[str] = Field(default_factory=list)


class PolicyViolation(BaseModel):
    """One concrete policy violation with the offending evidence named."""

    kind: Literal["protected_path", "forbidden_pattern"]
    offender: str
    rule: str
    path: str | None = None
    message: str


class PolicyResult(BaseModel):
    """Deterministic outcome of evaluating one attempt diff against a policy."""

    passed: bool
    violations: list[PolicyViolation] = Field(default_factory=list)
