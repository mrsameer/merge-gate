"""Model-free replay of a completed deterministic verdict (FR-010)."""

from __future__ import annotations

from mergegate.acceptance.verdict import compute_verdict
from mergegate.models import Verdict


def replay_verdict(original: Verdict) -> Verdict:
    """Recompute a verdict from recorded checks and inputs with no provider path.

    This module intentionally imports neither harnesses nor the acceptance
    engine.  Replaying the recorded deterministic state means no model call,
    shell command, or mutable workspace is needed.
    """
    replayed = compute_verdict(
        attempt_id=original.attempt_id,
        checks=original.checks,
        acceptance_input=original.acceptance_input,
        replay_of=original.attempt_id,
    )
    if replayed.acceptance_hash != original.acceptance_hash:
        raise ValueError("recorded verdict failed deterministic replay verification")
    return replayed
