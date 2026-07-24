from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from mergegate.acceptance.engine import run_acceptance_engine
from mergegate.config.settings import get_settings
from mergegate.criteria.contract import freeze_contract
from mergegate.criteria.generate import generate_hybrid_criteria
from mergegate.harness.stub import StubHarnessAdapter
from mergegate.ledger.store import RunStore
from mergegate.models import Attempt, Run, RunStatus
from mergegate.orchestrator.cost import accumulate_cost
from mergegate.orchestrator.gates import approve_final_gate
from mergegate.workspace.worktree import capture_diff, create_worktree


class RunOrchestrator:
    def __init__(self, store: RunStore, repo_path: Path) -> None:
        self.store = store
        self.repo_path = repo_path
        self.harness = StubHarnessAdapter()

    def generate_criteria(self, run: Run) -> Run:
        contract = generate_hybrid_criteria(
            run_id=run.id,
            objective=run.objective,
            repo_path=self.repo_path,
        )
        run.contract = contract
        run.status = RunStatus.AWAITING_GATE
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
        harness_result = self.harness.propose_changes(
            objective=run.objective,
            feedback=None,
            workspace=str(worktree.path),
        )
        run.cost = accumulate_cost(run.cost, harness_result)
        verdict = run_acceptance_engine(
            attempt_id=attempt_id,
            contract=run.contract,
            workspace=worktree.path,
        )
        attempt = Attempt(
            id=attempt_id,
            run_id=run.id,
            index=attempt_index,
            worktree_path=str(worktree.path),
            branch=worktree.branch,
            diff=capture_diff(worktree.path),
            changed_files=harness_result.changed_files,
            harness_log=harness_result.log,
            verdict=verdict,
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

    def approve_final_gate(self, run: Run) -> Run:
        return approve_final_gate(run, self.store)


def build_orchestrator(store: RunStore | None = None) -> RunOrchestrator:
    settings = get_settings()
    store = store or RunStore(settings.data_dir / "runs")
    return RunOrchestrator(store, settings.demo_repo_path.resolve())
