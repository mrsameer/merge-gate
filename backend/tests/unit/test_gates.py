"""Final merge human gate tests for T029.

Encodes the gate contract from tasks.md § T029 and the happy-path integration
test: approving the gate on a Run at `awaiting_gate` whose latest attempt
passed acceptance moves the Run to `SUCCESS` and records a mergeable reference,
while an approval without a passing verdict, or any action off the gate, is
refused (Principle IV — an exception never resolves to `SUCCESS`).
"""

import pytest

from mergegate.models import Attempt, Run, RunStatus, Verdict
from mergegate.models.budget import Budget, CostAccounting
from mergegate.orchestrator import runner
from mergegate.orchestrator.gates import GateError, approve_merge, reject_merge


def _make_attempt(
    *, passed: bool | None = True, index: int = 0, diff: str = "diff --git a b"
) -> Attempt:
    verdict: Verdict | None = None
    if passed is not None:
        verdict = Verdict(
            attempt_id=f"attempt-{index}",
            passed=passed,
            acceptance_hash="hash-abc",
            acceptance_input={},
        )
    return Attempt(
        id=f"attempt-{index}",
        run_id="run-1",
        index=index,
        worktree_path=f"/tmp/wt-{index}",
        branch=f"mergegate/run-1/attempt-{index}",
        diff=diff,
        changed_files=["src/foo.py"],
        harness_log="",
        verdict=verdict,
    )


def _make_run(
    *,
    status: RunStatus = RunStatus.AWAITING_GATE,
    attempts: list[Attempt] | None = None,
) -> Run:
    return Run(
        id="run-1",
        workflow_id="wf-loop",
        objective="demo",
        repo_ref="main@deadbeef",
        status=status,
        budgets=Budget(max_attempts=5, max_wall_clock_s=600, max_model_calls=50),
        attempts=attempts if attempts is not None else [],
        current_attempt=0,
        cost=CostAccounting(),
    )


def _awaiting_gate_run(attempts: list[Attempt]) -> Run:
    """Build a Run legally moved into `awaiting_gate` via `transition`."""
    run = _make_run(status=RunStatus.RUNNING, attempts=attempts)
    runner.transition(run, RunStatus.AWAITING_GATE)
    return run


# --- approve_merge -------------------------------------------------------


def test_approve_at_gate_with_passing_attempt_succeeds() -> None:
    attempt = _make_attempt(passed=True)
    run = _awaiting_gate_run([attempt])

    result = approve_merge(run)

    assert result is run
    assert run.status == RunStatus.SUCCESS
    assert run.branch == attempt.branch
    assert run.patch_ref == attempt.id
    assert run.ended_at is not None


def test_approve_uses_latest_attempt_for_mergeable_reference() -> None:
    first = _make_attempt(passed=False, index=0)
    latest = _make_attempt(passed=True, index=1)
    run = _awaiting_gate_run([first, latest])

    approve_merge(run)

    assert run.status == RunStatus.SUCCESS
    assert run.branch == latest.branch


def test_approve_when_not_awaiting_gate_raises() -> None:
    run = _make_run(status=RunStatus.RUNNING, attempts=[_make_attempt(passed=True)])

    with pytest.raises(GateError):
        approve_merge(run)

    assert run.status == RunStatus.RUNNING


def test_approve_with_no_verdict_raises_and_stays_at_gate() -> None:
    run = _awaiting_gate_run([_make_attempt(passed=None)])

    with pytest.raises(GateError):
        approve_merge(run)

    assert run.status == RunStatus.AWAITING_GATE


def test_approve_with_failing_verdict_never_succeeds() -> None:
    run = _awaiting_gate_run([_make_attempt(passed=False)])

    with pytest.raises(GateError):
        approve_merge(run)

    assert run.status != RunStatus.SUCCESS
    assert run.status == RunStatus.AWAITING_GATE


def test_approve_with_no_attempts_raises() -> None:
    run = _awaiting_gate_run([])

    with pytest.raises(GateError):
        approve_merge(run)

    assert run.status == RunStatus.AWAITING_GATE


# --- reject_merge --------------------------------------------------------


def test_reject_at_gate_maps_to_human_rejected() -> None:
    run = _awaiting_gate_run([_make_attempt(passed=True)])

    result = reject_merge(run, reason="not what we wanted")

    assert result is run
    assert run.status == RunStatus.HUMAN_REJECTED
    assert run.ended_at is not None


def test_reject_when_not_awaiting_gate_raises() -> None:
    run = _make_run(status=RunStatus.RUNNING, attempts=[_make_attempt(passed=True)])

    with pytest.raises(GateError):
        reject_merge(run)

    assert run.status == RunStatus.RUNNING
