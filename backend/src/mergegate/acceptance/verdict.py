"""T026 — Pure-function verdict computation.

Turns the ordered ``list[CheckResult]`` produced by the LLM-free acceptance
engine (T025) into a :class:`Verdict`: an overall pass/fail plus a
deterministic ``acceptance_hash`` that fingerprints the decision inputs.

Everything here is a **pure function** over recorded state — no I/O, no clock,
no randomness, no model calls, no global state. That is what makes replay
(a later task) sound: with the coding model disabled, replay feeds the same
``acceptance_input`` and the same normalized checks back through
:func:`acceptance_hash` and MUST get the identical digest. To guarantee that,
the hash is computed over the *deterministic* decision inputs only and
explicitly excludes non-reproducible capture fields (``stdout``, ``stderr``,
``duration_ms``), which vary run-to-run even when the decision does not.
"""

from __future__ import annotations

import hashlib
import json

from mergegate.models.verdict import CheckResult, Verdict

# Fields of a `CheckResult` that are stable across replay and therefore
# participate in the acceptance hash. Capture fields (`stdout`, `stderr`,
# `duration_ms`) are deliberately excluded so the digest is reproducible.
_HASH_STABLE_FIELDS: tuple[str, ...] = (
    "criterion_id",
    "step",
    "passed",
    "exit_code",
    "baseline_result",
)


def _normalize_check(check: CheckResult) -> dict[str, object]:
    """Project a check down to its replay-stable decision fields.

    ``step`` is reduced to its string value (a ``StrEnum`` member) and
    ``baseline_result`` likewise, so the projection is plain JSON-serializable
    data with no dependence on enum identity.
    """
    return {
        "criterion_id": check.criterion_id,
        "step": check.step.value,
        "passed": check.passed,
        "exit_code": check.exit_code,
        "baseline_result": (
            check.baseline_result.value if check.baseline_result is not None else None
        ),
    }


def acceptance_hash(
    checks: list[CheckResult],
    acceptance_input: dict,
) -> str:
    """Return the SHA-256 hex digest of the deterministic decision inputs.

    The digest covers ``acceptance_input`` plus a replay-stable projection of
    each check (see ``_HASH_STABLE_FIELDS``), serialized as canonical JSON
    (sorted keys, compact separators). Check order is preserved as given —
    the pipeline emits checks in a deterministic order — but the same decision
    always yields the same digest because non-deterministic capture fields are
    excluded.

    This helper is factored out so replay can recompute the identical hash
    from recorded state without recomputing a whole verdict.

    Args:
        checks: The checks whose stable fields fingerprint the decision.
        acceptance_input: The recorded deterministic inputs to the decision.

    Returns:
        A 64-character lowercase SHA-256 hex digest.
    """
    payload = {
        "acceptance_input": acceptance_input,
        "checks": [_normalize_check(check) for check in checks],
    }
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_verdict(
    *,
    attempt_id: str,
    checks: list[CheckResult],
    acceptance_input: dict,
    replay_of: str | None = None,
) -> Verdict:
    """Compute the deterministic :class:`Verdict` for an attempt.

    ``passed`` is ``True`` only when there is at least one check and every
    check passed. Zero checks is **not** a pass: per Constitution Principle IV,
    the absence of verification is not success — an attempt that ran no checks
    has proven nothing and must fail closed.

    Args:
        attempt_id: Identifier of the attempt this verdict is for.
        checks: The ordered checks produced by the acceptance engine.
        acceptance_input: Recorded deterministic inputs, included verbatim in
            both the verdict and the ``acceptance_hash``.
        replay_of: When this verdict is a replay of an earlier one, the id of
            that original attempt; otherwise ``None``.

    Returns:
        A :class:`Verdict` with the pass/fail decision and reproducible
        ``acceptance_hash``.
    """
    passed = len(checks) > 0 and all(check.passed for check in checks)
    return Verdict(
        attempt_id=attempt_id,
        passed=passed,
        checks=checks,
        acceptance_hash=acceptance_hash(checks, acceptance_input),
        acceptance_input=acceptance_input,
        replay_of=replay_of,
    )
