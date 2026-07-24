from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from mergegate.config.settings import get_settings
from mergegate.criteria.contract import freeze_contract
from mergegate.harness.stub import StubHarnessAdapter
from mergegate.ledger.store import RunStore
from mergegate.models import Attempt, Run, RunStatus, Verdict
from mergegate.orchestrator.cost import accumulate_cost
from mergegate.orchestrator.gates import approve_final_gate
from mergegate.orchestrator.nodes import (
    FourRoleNodeRunner,
    contract_from_success_criteria,
)
from mergegate.workspace.worktree import capture_diff, create_worktree


def _build_harness(provider: str):
    if provider == "stub":
        return StubHarnessAdapter()
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

    def start_run(self, run: Run) -> Run:
        if run.contract is None or not run.contract.approved:
            raise ValueError("contract not approved")
        run.status = RunStatus.RUNNING
        run.started_at = datetime.now(tz=UTC)
        attempt_index = run.current_attempt + 1
        worktree = create_worktree(self.repo_path)
        attempt_id = str(uuid4())

        ctx = self.nodes.execute_attempt(
            run=run,
            worktree_path=worktree.path,
            attempt_id=attempt_id,
            attempt_index=attempt_index,
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

        verdict = ctx.verdict
        if verdict is None:
            raise RuntimeError("validation node did not produce a verdict")

        attempt = Attempt(
            id=attempt_id,
            run_id=run.id,
            index=attempt_index,
            worktree_path=str(worktree.path),
            branch=worktree.branch,
            diff=capture_diff(worktree.path),
            changed_files=ctx.changed_files,
            harness_log=ctx.harness_log,
            verdict=verdict,
            evidence=ctx.evidence,
        )
        run.attempts.append(attempt)
        run.current_attempt = attempt_index
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
        else:
            run.status = RunStatus.EXHAUSTED
            run.ended_at = datetime.now(tz=UTC)
        return self.store.save(run)

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
