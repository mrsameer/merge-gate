from __future__ import annotations

import hashlib
import json
import re

from mergegate.models import CheckResult, StructuredFeedback, Verdict


def compute_failure_signature(verdict: Verdict) -> str:
    failed_ids = sorted(c.criterion_id for c in verdict.checks if not c.passed)
    messages = []
    for check in verdict.checks:
        if not check.passed:
            normalized = re.sub(r"\d+", "N", check.stderr + check.stdout)
            messages.append(normalized.strip())
    payload = json.dumps(
        {"criteria": failed_ids, "messages": sorted(messages)},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _first_failing_location(check: CheckResult) -> str:
    for line in (check.stderr + check.stdout).splitlines():
        if "FAILED" in line or "Error" in line or "assert" in line:
            return line.strip()[:200]
    return check.criterion_id


def build_failure_feedback(
    *,
    verdict: Verdict,
    attempt: int,
    command: str = "",
) -> StructuredFeedback | None:
    failing = next((check for check in verdict.checks if not check.passed), None)
    if failing is None:
        return None
    signature = compute_failure_signature(verdict)
    return StructuredFeedback(
        criterion=failing.criterion_id,
        command=command or failing.criterion_id,
        exit_code=failing.exit_code,
        failure_signature=signature,
        first_failing_location=_first_failing_location(failing),
        attempt=attempt,
    )
