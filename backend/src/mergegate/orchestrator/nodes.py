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

import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from mergegate.acceptance.baseline import run_baseline_checks
from mergegate.acceptance.commands import run_command
from mergegate.acceptance.engine import AcceptanceEngine
from mergegate.acceptance.evidence import build_red_green_evidence
from mergegate.acceptance.feedback import build_failure_feedback
from mergegate.acceptance.verdict import compute_verdict
from mergegate.harness.base import HarnessError
from mergegate.harness.registry import get_adapter
from mergegate.ledger.ledger import LedgerWriter
from mergegate.models import (
    Attempt,
    CheckResult,
    Contract,
    PassFail,
    Run,
    RunStatus,
    StructuredFeedback,
    Verdict,
)
from mergegate.orchestrator import cost as cost_accounting
from mergegate.orchestrator import runner
from mergegate.orchestrator.budgets import BudgetGuard, budget_reason
from mergegate.orchestrator.no_progress import NoProgressDetector
from mergegate.workspace.rollback import rollback_run
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
        ledger: Optional hash-chained ledger writer. When set, each attempt's
            accumulated `CostAccounting` is recorded through it (FR-022); when
            `None`, cost is still aggregated onto the run, just not persisted.
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
    ledger: LedgerWriter | None = None


def _emit(ctx: RunContext, event_type: str, payload: dict) -> None:
    if ctx.on_event is not None:
        ctx.on_event(event_type, payload)


def _accept_dir(worktree: Worktree, subdir: str) -> Path:
    """Directory the acceptance pipeline runs in for this worktree."""
    if subdir in ("", "."):
        return worktree.path
    return worktree.path / subdir


def _acceptance_input(contract: Contract, commit_sha: str) -> dict:
    """The frozen-contract projection recorded as the verdict's decision input."""
    return {
        "commit_sha": commit_sha,
        "validation_config": {"frozen_hash": contract.frozen_hash},
        "tool_versions": {"python": sys.version.split()[0]},
        "env_fingerprint": sys.platform,
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
    started = ctx.now()
    result = adapter.propose_changes(ctx.run.objective, feedback, worktree)
    elapsed = max(0.0, ctx.now() - started)

    # Rebind (not in-place mutate) so a concurrently polling GET always
    # serializes a whole accounting, and persist the snapshot when a ledger
    # is wired (T074/FR-022).
    ctx.run.cost = cost_accounting.add_result(ctx.run.cost, result, elapsed)
    if ctx.ledger is not None:
        cost_accounting.record_cost(ctx.ledger, ctx.run.cost)

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


def run_validation_node(
    ctx: RunContext,
    attempt: Attempt,
    accept_dir: Path,
    baseline_checks: list[CheckResult],
) -> Verdict:
    """Run the contract through the acceptance engine and attach the verdict."""
    checks = ctx.engine.run(ctx.contract, str(accept_dir))
    baseline_by_criterion = {check.criterion_id: check for check in baseline_checks}
    checks = [
        check.model_copy(
            update={
                "baseline_result": PassFail.FAIL
                if not baseline_by_criterion[check.criterion_id].passed
                else PassFail.PASS
            }
        )
        if check.criterion_id in baseline_by_criterion
        else check
        for check in checks
    ]
    evidence = build_red_green_evidence(ctx.contract, baseline_checks, checks)
    attempt.red_green_evidence = evidence.model_dump(mode="json")
    commit_sha = run_command(
        ["git", "rev-parse", "HEAD"], cwd=str(accept_dir)
    ).stdout.strip()
    verdict = compute_verdict(
        attempt_id=attempt.id,
        checks=checks,
        acceptance_input=_acceptance_input(ctx.contract, commit_sha),
    )
    attempt.verdict = verdict
    return verdict


def _build_feedback(
    contract: Contract, attempt: Attempt, index: int
) -> StructuredFeedback:
    """Turn the first failing check into structured feedback for the next plan."""
    verdict = attempt.verdict
    checks = verdict.checks if verdict is not None else []
    commands = {
        criterion.id: criterion.command or criterion.id
        for criterion in contract.criteria
    }
    return build_failure_feedback(checks, commands=commands, attempt=index)


def _terminate(
    ctx: RunContext,
    status: RunStatus,
    *,
    reason: str,
    active_worktree: Worktree | None = None,
    baseline_status: str | None = None,
) -> None:
    """Move the run to a terminal state (once), emitting a terminal event."""
    if not runner.is_terminal(ctx.run.status):
        runner.transition(ctx.run, status)
    report = rollback_run(
        ctx.run,
        active_worktree=active_worktree,
        reason=reason,
        baseline_status=baseline_status,
    )
    _emit(
        ctx,
        "terminal",
        {
            "status": ctx.run.status.value,
            "reason": reason,
            "undelivered_report": report,
        },
    )


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
    guard = BudgetGuard(
        max_attempts=budgets.max_attempts,
        max_wall_clock_s=budgets.max_wall_clock_s,
        max_model_calls=budgets.max_model_calls,
        now=ctx.now,
    )
    guard.start()
    detector = NoProgressDetector()
    active_worktree: Worktree | None = None
    baseline_status = run_command(
        ["git", "status", "--porcelain"], cwd=ctx.repo_ref
    ).stdout

    try:
        while True:
            exhausted = guard.terminal_status(
                attempts=run.current_attempt, model_calls=run.cost.model_calls
            )
            if exhausted is not None:
                _terminate(
                    ctx,
                    exhausted,
                    reason=budget_reason(
                        exhausted,
                        attempts=run.current_attempt,
                        model_calls=run.cost.model_calls,
                        max_attempts=budgets.max_attempts,
                        max_model_calls=budgets.max_model_calls,
                    ),
                    active_worktree=active_worktree,
                    baseline_status=baseline_status,
                )
                return

            index = run.current_attempt + 1
            _emit(ctx, "node_status", {"node": "baseline", "attempt": index})
            try:
                baseline_checks = run_baseline_checks(
                    ctx.contract, ctx.repo_ref, ctx.engine
                )
            except ValueError:
                _terminate(
                    ctx,
                    RunStatus.NO_PROGRESS,
                    reason="baseline proof invalid",
                    baseline_status=baseline_status,
                )
                return
            _emit(ctx, "node_status", {"node": "execution", "attempt": index})
            try:
                attempt, active_worktree = run_execution_node(ctx, index, feedback)
            except HarnessError as exc:
                _terminate(
                    ctx,
                    RunStatus.NO_PROGRESS,
                    reason=f"harness could not run: {exc}"[:1000],
                    baseline_status=baseline_status,
                )
                return

            run.current_attempt = index
            # Rebind (not in-place append) so a concurrently polling GET always
            # serializes a complete list, never one mid-mutation.
            run.attempts = [*run.attempts, attempt]

            _emit(ctx, "node_status", {"node": "validation", "attempt": index})
            verdict = run_validation_node(
                ctx,
                attempt,
                _accept_dir(active_worktree, ctx.workspace_subdir),
                baseline_checks,
            )
            _emit(ctx, "verdict", {"attempt": index, "passed": verdict.passed})

            if verdict.passed:
                runner.transition(run, RunStatus.AWAITING_GATE)
                _emit(ctx, "gate", {"attempt": index, "gate": "merge"})
                return

            feedback = _build_feedback(ctx.contract, attempt, index)
            if detector.observe(feedback.failure_signature, attempt.diff):
                _terminate(
                    ctx,
                    RunStatus.NO_PROGRESS,
                    reason="no progress detected",
                    active_worktree=active_worktree,
                    baseline_status=baseline_status,
                )
                return

            exhausted = guard.terminal_status(
                attempts=run.current_attempt, model_calls=run.cost.model_calls
            )
            if exhausted is not None:
                _terminate(
                    ctx,
                    exhausted,
                    reason=budget_reason(
                        exhausted,
                        attempts=run.current_attempt,
                        model_calls=run.cost.model_calls,
                        max_attempts=budgets.max_attempts,
                        max_model_calls=budgets.max_model_calls,
                    ),
                    active_worktree=active_worktree,
                    baseline_status=baseline_status,
                )
                return
            _emit(
                ctx,
                "retry",
                {
                    "attempt": index + 1,
                    "max_attempts": budgets.max_attempts,
                    "reason": "acceptance failed",
                    "feedback": feedback.model_dump(mode="json"),
                },
            )
            discard_worktree(active_worktree)
            active_worktree = None
    except Exception:
        # Principle IV: no exception path may leave the run non-terminal or
        # resolve it to SUCCESS.
        if not runner.is_terminal(run.status):
            _terminate(
                ctx,
                RunStatus.NO_PROGRESS,
                reason="unexpected orchestration failure",
                active_worktree=active_worktree,
                baseline_status=baseline_status,
            )
        return
