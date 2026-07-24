from __future__ import annotations

from pathlib import Path

from mergegate.acceptance.engine import run_acceptance_engine
from mergegate.models import Contract, Verdict


def replay_verdict(
    *,
    original: Verdict,
    contract: Contract,
    workspace: Path,
    replay_attempt_id: str,
) -> Verdict:
    """Recompute a verdict from recorded acceptance input with zero harness calls."""
    if original.acceptance_input is None:
        raise ValueError("original verdict missing acceptance_input")
    recomputed = run_acceptance_engine(
        attempt_id=replay_attempt_id,
        contract=contract,
        workspace=workspace,
        commit_sha=original.acceptance_input.commit_sha,
    )
    if recomputed.acceptance_hash != original.acceptance_hash:
        raise RuntimeError(
            "replay acceptance_hash mismatch: "
            f"{recomputed.acceptance_hash} != {original.acceptance_hash}"
        )
    return recomputed.model_copy(
        update={
            "passed": original.passed,
            "acceptance_hash": original.acceptance_hash,
            "replay_of": original.acceptance_hash,
        }
    )
