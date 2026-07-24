from __future__ import annotations

import hashlib
import json

from mergegate.models import AcceptanceInput, CheckResult, Verdict


def compute_acceptance_hash(acceptance_input: AcceptanceInput) -> str:
    payload = acceptance_input.model_dump(mode="json")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def compute_verdict(
    *,
    attempt_id: str,
    checks: list[CheckResult],
    acceptance_input: AcceptanceInput,
    replay_of: str | None = None,
) -> Verdict:
    passed = all(check.passed for check in checks)
    acceptance_hash = compute_acceptance_hash(acceptance_input)
    return Verdict(
        attempt_id=attempt_id,
        passed=passed,
        checks=checks,
        acceptance_hash=acceptance_hash,
        acceptance_input=acceptance_input,
        replay_of=replay_of,
    )
