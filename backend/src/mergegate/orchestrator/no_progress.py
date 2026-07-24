from __future__ import annotations

import hashlib

from mergegate.models import Attempt


def normalize_diff(diff: str) -> str:
    lines = [line for line in diff.splitlines() if not line.startswith("index ")]
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def detect_no_progress(previous: Attempt, current: Attempt) -> bool:
    if previous.failure_signature is None or current.failure_signature is None:
        return False
    if previous.failure_signature != current.failure_signature:
        return False
    return normalize_diff(previous.diff) == normalize_diff(current.diff)
