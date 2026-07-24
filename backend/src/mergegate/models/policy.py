"""Anti-cheat policy configuration (FR-017, FR-018)."""

from pydantic import BaseModel, Field


class Policy(BaseModel):
    """Protected paths and forbidden diff patterns enforced pre-acceptance."""

    protected_paths: list[str] = Field(default_factory=list)
    forbidden_diff_patterns: list[str] = Field(default_factory=list)
