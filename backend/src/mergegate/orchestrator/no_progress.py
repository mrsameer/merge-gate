"""Failure-signature and consecutive no-progress detection (US3/T041)."""

from __future__ import annotations

import hashlib
import re

from mergegate.models import CheckResult


def failure_signature(check: CheckResult) -> str:
    """Return a stable identifier for the deterministic failure cause."""
    output = (check.stderr or check.stdout).strip()
    normalized = re.sub(r"\s+", " ", output)
    payload = f"{check.criterion_id}\0{check.exit_code}\0{normalized}".encode()
    return hashlib.sha256(payload).hexdigest()


class NoProgressDetector:
    """Fire only for consecutive matching failures with an unchanged diff."""

    def __init__(self) -> None:
        self._previous: tuple[str, str] | None = None

    def observe(self, signature: str, diff: str) -> bool:
        current = (signature, diff)
        no_progress = current == self._previous
        self._previous = current
        return no_progress
