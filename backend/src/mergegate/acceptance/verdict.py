"""T026 — Pure verdict computation over recorded acceptance state.

The acceptance engine (T025) runs the ordered check pipeline and captures
``CheckResult`` records. This module is the *only* place the final pass/fail
decision and ``acceptance_hash`` are derived from that recorded state.

It is intentionally pure: no subprocesses, no filesystem access, no model
calls. Identical ``(checks, acceptance_input)`` always yields an identical
``Verdict`` (Constitution Principle II, FR-006/FR-010), which is what makes
zero-model replay possible (T034).
"""

from __future__ import annotations

import hashlib

from mergegate.ledger.ledger import canonical_json
from mergegate.models import CheckResult, Verdict

ACCEPTANCE_INPUT_KEYS: tuple[str, ...] = (
    "commit_sha",
    "validation_config",
    "tool_versions",
    "env_fingerprint",
)


def build_acceptance_input(
    *,
    commit_sha: str,
    validation_config: dict,
    tool_versions: dict,
    env_fingerprint: str,
) -> dict:
    """Build the replayable acceptance input bundle (FR-010)."""
    if not commit_sha.strip():
        raise ValueError("commit_sha must be a non-empty string")
    if not env_fingerprint.strip():
        raise ValueError("env_fingerprint must be a non-empty string")

    return {
        "commit_sha": commit_sha,
        "validation_config": dict(validation_config),
        "tool_versions": dict(tool_versions),
        "env_fingerprint": env_fingerprint,
    }


def compute_acceptance_hash(acceptance_input: dict) -> str:
    """Return ``H(canonical(acceptance_input))`` for replay verification."""
    _validate_acceptance_input(acceptance_input)
    digest = canonical_json(acceptance_input).encode("utf-8")
    return hashlib.sha256(digest).hexdigest()


def compute_verdict(
    attempt_id: str,
    checks: list[CheckResult],
    acceptance_input: dict,
    *,
    replay_of: str | None = None,
) -> Verdict:
    """Compute the deterministic verdict for one attempt.

    ``passed`` is true only when at least one check was recorded and every
    check passed. An empty check list is treated as failure so vacuous success
    is impossible (Principle IV).
    """
    if not attempt_id.strip():
        raise ValueError("attempt_id must be a non-empty string")

    _validate_acceptance_input(acceptance_input)
    passed = bool(checks) and all(check.passed for check in checks)

    return Verdict(
        attempt_id=attempt_id,
        passed=passed,
        checks=list(checks),
        acceptance_hash=compute_acceptance_hash(acceptance_input),
        acceptance_input=dict(acceptance_input),
        replay_of=replay_of,
    )


def _validate_acceptance_input(acceptance_input: dict) -> None:
    missing = [key for key in ACCEPTANCE_INPUT_KEYS if key not in acceptance_input]
    if missing:
        joined = ", ".join(missing)
        raise ValueError(
            f"acceptance_input is missing required field(s): {joined}"
        )
