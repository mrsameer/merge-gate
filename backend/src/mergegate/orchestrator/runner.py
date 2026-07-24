from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from mergegate.acceptance.feedback import build_failure_feedback
from mergegate.config.settings import get_settings
from mergegate.criteria.consistency import detect_contradictions
from mergegate.criteria.contract import freeze_contract
from mergegate.harness.stub import (
    AlwaysFailHarnessAdapter,
    NoProgressHarnessAdapter,
    StubHarnessAdapter,
)
from mergegate.ledger.store import RunStore
from mergegate.models import (
    Attempt,
    ClarificationRequest,
    Run,
    RunStatus,
    StructuredFeedback,
    Verdict,
)
from mergegate.orchestrator.budgets import budget_exhausted
from mergegate.orchestrator.cost import accumulate_cost
from mergegate.orchestrator.gates import approve_final_gate
from mergegate.orchestrator.no_progress import detect_no_progress
from mergegate.orchestrator.nodes import (
    FourRoleNodeRunner,
    contract_from_success_criteria,
)
from mergegate.workspace.rollback import rollback_run
from mergegate.workspace.worktree import capture_attempt_diff, create_worktree


def _build_harness(provider: str):
    if provider == "stub":
        return StubHarnessAdapter()
    if provider == "stub-fail":
        return AlwaysFailHarnessAdapter()
    if provider == "stub-no-progress":
        return NoProgressHarnessAdapter()
    raise ValueError(f"unsupported harness provider: {provider}")


class RunOrchestrator:
    def __init__(
        self, store: RunStore, repo_path: Path, *, harness_provider: str
    ) -> None:
        self.store = store
        self.repo_path = repo_path
        harness = _build_harness(harness_provider)
        self.nodes = FourRoleNodeRunner(harness=harness, repo_path=repo_path)

    def generate_criteria(self, run: Run) -> Run:
        result = self.nodes.run_success_criteria(run)
        contract = contract_from_success_criteria(result)
        run.contract = contract
        run.status = RunStatus.AWAITING_GATE
        self.store.ledger.append(
            run.id,
            "node_status",
            {
                "node_id": result.node_id,
                "role": result.role.value,
                "status": result.status,
            },
        )
        self.store.ledger.append(run.id, "contract", {"contract_id": contract.id})
        return self.store.save(run)

    def approve_contract(self, run: Run) -> Run:
        if run.contract is None:
            raise ValueError("contract missing")
        run.contract = freeze_contract(run.contract)
        run.status = RunStatus.AWAITING_GATE
        self.store.ledger.append(
            run.id,
            "gate",
            {
                "kind": "contract",
                "state": "approved",
                "frozen_hash": run.contract.frozen_hash,
            },
        )
        return self.store.save(run)

    def _criterion_command(self, run: Run, criterion_id: str) -> str:
        if run.contract is None:
            return criterion_id
        for criterion in run.contract.criteria:
            if criterion.id == criterion_id:
                return criterion.command or criterion_id
        return criterion_id

    def _record_attempt(
        self,
        *,
        run: Run,
        ctx,
        worktree,
        attempt_id: str,
        attempt_index: int,
    ) -> Attempt:
        verdict = ctx.verdict
        if verdict is None:
            raise RuntimeError("validation node did not produce a verdict")
        command = ""
        if verdict.checks:
            failing = next((c for c in verdict.checks if not c.passed), None)
            if failing:
                command = self._criterion_command(run, failing.criterion_id)
        feedback = build_failure_feedback(
            verdict=verdict,
            attempt=attempt_index,
            command=command,
        )
        attempt = Attempt(
            id=attempt_id,
            run_id=run.id,
            index=attempt_index,
            worktree_path=str(worktree.path),
            branch=worktree.branch,
            diff=capture_attempt_diff(worktree.path, ctx.changed_files),
            changed_files=ctx.changed_files,
            harness_log=ctx.harness_log,
            verdict=verdict,
            evidence=ctx.evidence,
            feedback=feedback if not verdict.passed else None,
            failure_signature=feedback.failure_signature if feedback else None,
        )
        return attempt

    def _terminate_undelivered(
        self,
        run: Run,
        *,
        worktrees: list[Path],
        reason: str,
        status: RunStatus,
    ) -> Run:
        run.undelivered_report = rollback_run(
            run=run,
            repo_path=self.repo_path,
            worktrees=worktrees,
            reason=reason,
        )
        run.status = status
        run.ended_at = datetime.now(tz=UTC)
        self.store.ledger.append(
            run.id,
            "terminal",
            {"state": status.value, "reason": reason},
        )
        return self.store.save(run)

    def _terminate_clarification(
        self, run: Run, clarification: ClarificationRequest
    ) -> Run:
        run.clarification_request = clarification
        run.status = RunStatus.CLARIFICATION_REQUIRED
        run.ended_at = datetime.now(tz=UTC)
        payload = clarification.model_dump(mode="json")
        self.store.ledger.append(run.id, "clarification", payload)
        self.store.ledger.append(
            run.id,
            "terminal",
            {
                "state": RunStatus.CLARIFICATION_REQUIRED.value,
                "reason": clarification.reason,
            },
        )
        return self.store.save(run)

    def start_run(self, run: Run) -> Run:
        if run.contract is None or not run.contract.approved:
            raise ValueError("contract not approved")

        clarification = detect_contradictions(run.contract, objective=run.objective)
        if clarification is not None:
            return self._terminate_clarification(run, clarification)

        run.status = RunStatus.RUNNING
        run.started_at = datetime.now(tz=UTC)
        run.undelivered_report = None

        feedback: StructuredFeedback | None = None
        worktrees: list[Path] = []

        while True:
            exhausted = budget_exhausted(run, started_at=run.started_at)
            if exhausted is not None:
                return self._terminate_undelivered(
                    run,
                    worktrees=worktrees,
                    reason=exhausted,
                    status=RunStatus.EXHAUSTED,
                )

            attempt_index = run.current_attempt + 1
            worktree = create_worktree(self.repo_path)
            worktrees.append(worktree.path)
            attempt_id = str(uuid4())

            ctx = self.nodes.execute_attempt(
                run=run,
                worktree_path=worktree.path,
                attempt_id=attempt_id,
                attempt_index=attempt_index,
                feedback=feedback,
            )
            harness_result = ctx.harness_result
            if harness_result is None:
                raise RuntimeError("execution node did not produce harness output")
            run.cost = accumulate_cost(run.cost, harness_result)

            for node_result in ctx.node_results:
                self.store.ledger.append(
                    run.id,
                    "node_status",
                    {
                        "node_id": node_result.node_id,
                        "role": node_result.role.value,
                        "status": node_result.status,
                        "attempt": attempt_index,
                    },
                )

            attempt = self._record_attempt(
                run=run,
                ctx=ctx,
                worktree=worktree,
                attempt_id=attempt_id,
                attempt_index=attempt_index,
            )
            run.attempts.append(attempt)
            run.current_attempt = attempt_index

            verdict = attempt.verdict
            assert verdict is not None
            self.store.ledger.append(
                run.id,
                "verdict",
                {
                    "attempt": attempt_index,
                    "passed": verdict.passed,
                    "acceptance_hash": verdict.acceptance_hash,
                },
            )

            if verdict.passed:
                run.status = RunStatus.AWAITING_FINAL_GATE
                run.branch_ref = worktree.branch
                return self.store.save(run)

            if len(run.attempts) >= 2 and detect_no_progress(
                run.attempts[-2], run.attempts[-1]
            ):
                return self._terminate_undelivered(
                    run,
                    worktrees=worktrees,
                    reason="no_progress",
                    status=RunStatus.NO_PROGRESS,
                )

            if attempt.feedback is not None:
                feedback = attempt.feedback
                self.store.ledger.append(
                    run.id,
                    "retry",
                    {
                        "attempt": attempt_index,
                        "failure_signature": attempt.failure_signature,
                        "feedback": attempt.feedback.model_dump(mode="json"),
                    },
                )

            if run.current_attempt >= run.budgets.max_attempts:
                return self._terminate_undelivered(
                    run,
                    worktrees=worktrees,
                    reason="max_attempts",
                    status=RunStatus.EXHAUSTED,
                )

    def replay_run(self, run: Run) -> Verdict:
        if run.contract is None:
            raise ValueError("contract missing")
        if not run.attempts:
            raise ValueError("no attempts to replay")
        attempt = run.attempts[-1]
        if attempt.verdict is None:
            raise ValueError("attempt missing verdict")
        if not attempt.worktree_path:
            raise ValueError("attempt missing worktree_path")

        from mergegate.acceptance.replay import replay_verdict

        replayed = replay_verdict(
            original=attempt.verdict,
            contract=run.contract,
            workspace=Path(attempt.worktree_path),
            replay_attempt_id=f"replay-{attempt.id}",
        )
        self.store.ledger.append(
            run.id,
            "replay",
            {
                "attempt": attempt.index,
                "acceptance_hash": replayed.acceptance_hash,
                "model_calls": 0,
            },
        )
        return replayed

    def approve_final_gate(self, run: Run) -> Run:
        return approve_final_gate(run, self.store)


def build_orchestrator(store: RunStore | None = None) -> RunOrchestrator:
    settings = get_settings()
    store = store or RunStore(settings.data_dir / "runs")
    return RunOrchestrator(
        store,
        settings.demo_repo_path.resolve(),
        harness_provider=settings.harness_provider,
    )
