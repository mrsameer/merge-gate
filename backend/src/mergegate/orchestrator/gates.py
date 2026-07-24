"""Final merge human gate (T029, tasks.md § T029).

The gate is the last human checkpoint before a Run is declared merged. It is
pure and deterministic — no I/O, no model calls — operating over a `Run` and
mutating its status through `runner.transition` so the Run state machine
(FR-025) stays the single source of truth for what moves are legal.

Two operator actions are exposed:

- `approve_merge`: only valid when the Run is `awaiting_gate` AND the latest
  attempt carries a passing `Verdict`. Principle IV forbids merging an
  unverified or failed attempt, so an approval without a passing verdict is
  refused rather than silently resolved to `SUCCESS`. On success the Run
  transitions to `SUCCESS` and records the mergeable reference (`branch` /
  `patch_ref`) taken from that passing attempt.
- `reject_merge`: valid whenever the Run is `awaiting_gate`; transitions the
  Run to `HUMAN_REJECTED`.
"""

from mergegate.models import Attempt, Run, RunStatus
from mergegate.orchestrator import runner


class GateError(RuntimeError):
    """Raised when a gate action is invalid for the Run's current state.

    Examples: approving or rejecting a Run that is not `awaiting_gate`, or
    approving when the latest attempt has no verdict or a failing verdict.
    """


def _latest_passing_attempt(run: Run) -> Attempt:
    """Return the latest attempt for `run`, requiring a passing verdict.

    Raises `GateError` if the Run has no attempts, or if the latest attempt
    has no verdict or a verdict that did not pass — you cannot merge an
    unverified or failed attempt (Principle IV).
    """
    if not run.attempts:
        raise GateError(f"run {run.id} has no attempts to merge")

    latest = run.attempts[-1]
    if latest.verdict is None:
        raise GateError(
            f"run {run.id} latest attempt {latest.id} has no verdict; "
            "cannot merge an unverified attempt"
        )
    if not latest.verdict.passed:
        raise GateError(
            f"run {run.id} latest attempt {latest.id} did not pass acceptance; "
            "cannot merge a failed attempt"
        )
    return latest


def approve_merge(run: Run) -> Run:
    """Approve the final merge gate, moving `run` to `SUCCESS`.

    Preconditions: `run` is `awaiting_gate` and its latest attempt has a
    passing `Verdict`. On success the Run transitions to `RunStatus.SUCCESS`
    and its mergeable reference is recorded from that attempt — `run.branch`
    from the attempt's `branch`, and `run.patch_ref` from the attempt's id
    when it carries a diff.

    Raises `GateError` if the Run is not at the gate or the latest attempt
    did not pass. Returns the same (mutated) `Run` for convenience.
    """
    if run.status != RunStatus.AWAITING_GATE:
        raise GateError(
            f"cannot approve merge for run {run.id} in status {run.status}; "
            "run must be awaiting_gate"
        )

    attempt = _latest_passing_attempt(run)
    runner.transition(run, RunStatus.SUCCESS)
    run.branch = attempt.branch
    run.patch_ref = attempt.id if attempt.diff else None
    return run


def reject_merge(run: Run, reason: str | None = None) -> Run:
    """Reject the final merge gate, moving `run` to `HUMAN_REJECTED`.

    Precondition: `run` is `awaiting_gate`. `reason` is accepted for caller
    ergonomics (e.g. audit logging by the caller) but is not persisted here,
    keeping this function free of I/O. Raises `GateError` if the Run is not at
    the gate. Returns the same (mutated) `Run` for convenience.
    """
    if run.status != RunStatus.AWAITING_GATE:
        raise GateError(
            f"cannot reject merge for run {run.id} in status {run.status}; "
            "run must be awaiting_gate"
        )

    runner.transition(run, RunStatus.HUMAN_REJECTED)
    return run
