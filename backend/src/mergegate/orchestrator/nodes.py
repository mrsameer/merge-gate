"""T027 — Node behaviours and the bounded attempt-loop run driver.

This is where the four-role loop actually *runs* an objective. The graph
(`graph.py`) owns structural assembly and the runner (`runner.py`) owns the
generic Run state machine; this module owns *what each node does* and the
budget-bounded loop that drives them:

* **execution** — creates a fresh isolated `Worktree` from the run's repo,
  asks the configured `HarnessAdapter` to propose changes, records the
  `Attempt` (diff / changed files / log / branch), and accumulates the
  harness's token/model-call/USD usage into the run's `CostAccounting`
  (T074). A `HarnessError` (the harness could not run at all) routes to the
  `NO_PROGRESS` terminal — never to success (Principle IV).
* **validation** — runs the frozen contract through the *separate* LLM-free
  acceptance engine over the attempt's worktree and computes a deterministic
  `Verdict` (Principle I: the verdict comes from command exit codes, not the
  coding agent).
* **decision** — passing verdict -> the final merge gate (`awaiting_gate`);
  failing verdict -> retry from planning while attempts and wall-clock remain,
  otherwise a bounded terminal (`EXHAUSTED` / `TIMED_OUT`).

`drive_run` is the entry point the API calls (in a background thread). It
leaves a successful run at `awaiting_gate`; the human merge gate
(`gates.approve_merge`) resumes it to `SUCCESS`.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from mergegate.acceptance.engine import AcceptanceEngine
from mergegate.acceptance.verdict import compute_verdict
from mergegate.harness.base import HarnessError
from mergegate.harness.registry import get_adapter
from mergegate.models import (
    Attempt,
    Contract,
    Run,
    RunStatus,
    StructuredFeedback,
    Verdict,
)
from mergegate.orchestrator import runner
from mergegate.workspace.worktree import Worktree, create_worktree, discard_worktree

EventSink = Callable[[str, dict], None]


@dataclass
class RunContext:
    """Everything the run driver needs to execute one run's bounded loop.

    Attributes:
        run: The `Run` being driven (mutated in place as attempts execute).
        contract: The frozen, approved acceptance contract.
        provider: Harness provider name (e.g. ``"scripted"`` for tests).
        repo_ref: Filesystem path to the base repository to branch from.
        workspace_subdir: Path of the project within its git top-level, so the
            acceptance pipeline runs in the right directory when the repo is a
            subdirectory of a larger checkout (``"."`` = the worktree root).
        adapter_kwargs: Extra kwargs forwarded to `get_adapter` (e.g. the
            scripted diff/file set).
        engine: The acceptance engine used by the validation node.
        now: Monotonic time source (injectable so the zero-budget timeout can
            be exercised deterministically).
        worktrees_root: Optional root under which per-attempt worktrees are
            created; defaults to a fresh temp dir per worktree.
        on_event: Optional sink for streaming node/verdict/terminal events.
    """

    run: Run
    contract: Contract
    provider: str
    repo_ref: str
    workspace_subdir: str = "."
    adapter_kwargs: dict = field(default_factory=dict)
    engine: AcceptanceEngine = field(default_factory=AcceptanceEngine)
    now: Callable[[], float] = time.monotonic
    worktrees_root: Path | None = None
    on_event: EventSink | None = None


def _emit(ctx: RunContext, event_type: str, payload: dict) -> None:
    if ctx.on_event is not None:
        ctx.on_event(event_type, payload)


def _accept_dir(worktree: Worktree, subdir: str) -> Path:
    """Directory the acceptance pipeline runs in for this worktree."""
    if subdir in ("", "."):
        return worktree.path
    return worktree.path / subdir


def _acceptance_input(contract: Contract) -> dict:
    """The frozen-contract projection recorded as the verdict's decision input."""
    return {
        "contract_id": contract.id,
        "frozen_hash": contract.frozen_hash,
        "criteria": [
            {
                "id": criterion.id,
                "type": criterion.type.value,
                "priority": criterion.priority,
                "step": criterion.step.value if criterion.step else None,
            }
            for criterion in sorted(contract.criteria, key=lambda c: c.priority)
        ],
    }


def run_execution_node(
    ctx: RunContext, index: int, feedback: StructuredFeedback | None
) -> tuple[Attempt, Worktree]:
    """Execute one attempt: isolate a worktree, propose changes, record usage.

    Raises:
        HarnessError: If the harness could not be invoked at all.
    """
    branch = f"mergegate/{ctx.run.id}/attempt-{index}"
    worktree = create_worktree(
        ctx.repo_ref, branch=branch, worktrees_root=ctx.worktrees_root
    )
    adapter = get_adapter(ctx.provider, **ctx.adapter_kwargs)
    result = adapter.propose_changes(ctx.run.objective, feedback, worktree)

    ctx.run.cost.tokens += result.tokens
    ctx.run.cost.model_calls += result.model_calls
    ctx.run.cost.usd += result.usd

    attempt = Attempt(
        id=str(uuid4()),
        run_id=ctx.run.id,
        index=index,
        worktree_path=str(worktree.path),
        branch=worktree.branch,
        diff=result.diff,
        changed_files=result.changed_files,
        harness_log=result.log,
    )
    return attempt, worktree


def run_validation_node(ctx: RunContext, attempt: Attempt, accept_dir: Path) -> Verdict:
    """Run the contract through the acceptance engine and attach the verdict."""
    checks = ctx.engine.run(ctx.contract, str(accept_dir))
    verdict = compute_verdict(
        attempt_id=attempt.id,
        checks=checks,
        acceptance_input=_acceptance_input(ctx.contract),
    )
    attempt.verdict = verdict
    return verdict


def _build_feedback(attempt: Attempt, index: int) -> StructuredFeedback:
    """Turn the first failing check into structured feedback for the next plan."""
    verdict = attempt.verdict
    failed = None
    if verdict is not None:
        failed = next((check for check in verdict.checks if not check.passed), None)
    if failed is None:
        return StructuredFeedback(
            criterion="",
            command="",
            exit_code=1,
            failure_signature="no failing check recorded",
            attempt=index,
        )
    signature = (failed.stderr or failed.stdout or "").strip()
    return StructuredFeedback(
        criterion=failed.criterion_id,
        command=failed.criterion_id,
        exit_code=failed.exit_code,
        failure_signature=signature[:500] or f"check {failed.criterion_id} failed",
        first_failing_location=None,
        attempt=index,
    )


def _terminate(ctx: RunContext, status: RunStatus) -> None:
    """Move the run to a terminal state (once), emitting a terminal event."""
    if not runner.is_terminal(ctx.run.status):
        runner.transition(ctx.run, status)
    _emit(ctx, "terminal", {"status": ctx.run.status.value})


def drive_run(ctx: RunContext) -> None:
    """Drive the bounded attempt loop to a gate or a terminal state.

    On a passing verdict the run is left at ``awaiting_gate`` for the human
    merge gate. On exhausted attempts / wall-clock / model-call budgets it
    stops at a bounded terminal state; a harness that cannot run stops at
    ``NO_PROGRESS``. A crash never resolves to ``SUCCESS`` (Principle IV).
    """
    run = ctx.run
    budgets = run.budgets
    feedback: StructuredFeedback | None = None
    deadline = ctx.now() + budgets.max_wall_clock_s

    try:
        while True:
            if budgets.max_wall_clock_s <= 0 or ctx.now() >= deadline:
                _terminate(ctx, RunStatus.TIMED_OUT)
                return
            if run.current_attempt >= budgets.max_attempts:
                _terminate(ctx, RunStatus.EXHAUSTED)
                return
            if run.cost.model_calls >= budgets.max_model_calls:
                _terminate(ctx, RunStatus.EXHAUSTED)
                return

            index = run.current_attempt + 1
            _emit(ctx, "node_status", {"node": "execution", "attempt": index})
            try:
                attempt, worktree = run_execution_node(ctx, index, feedback)
            except HarnessError:
                _terminate(ctx, RunStatus.NO_PROGRESS)
                return

            run.current_attempt = index
            # Rebind (not in-place append) so a concurrently polling GET always
            # serializes a complete list, never one mid-mutation.
            run.attempts = [*run.attempts, attempt]

            _emit(ctx, "node_status", {"node": "validation", "attempt": index})
            verdict = run_validation_node(
                ctx, attempt, _accept_dir(worktree, ctx.workspace_subdir)
            )
            _emit(ctx, "verdict", {"attempt": index, "passed": verdict.passed})

            if verdict.passed:
                runner.transition(run, RunStatus.AWAITING_GATE)
                _emit(ctx, "gate", {"attempt": index, "gate": "merge"})
                return

            discard_worktree(worktree)
            feedback = _build_feedback(attempt, index)

            if run.current_attempt >= budgets.max_attempts:
                _terminate(ctx, RunStatus.EXHAUSTED)
                return
            if ctx.now() >= deadline:
                _terminate(ctx, RunStatus.TIMED_OUT)
                return
    except Exception:
        # Principle IV: no exception path may leave the run non-terminal or
        # resolve it to SUCCESS.
        if not runner.is_terminal(run.status):
            _terminate(ctx, RunStatus.NO_PROGRESS)
        return
