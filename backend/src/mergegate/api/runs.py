"""T028 — the Runs REST surface (create / status / criteria / start / gate).

Implements the contract-before-code lifecycle promised by
`contracts/control-plane-api.md`:

    POST /api/runs                          create a run (at the contract gate)
    GET  /api/runs/{id}                     run status incl. cost + attempts
    POST /api/runs/{id}/criteria:generate   hybrid criteria grounded in files
    PUT  /api/runs/{id}/criteria            edit/prioritize (pre-approval only)
    POST /api/runs/{id}/criteria:approve    freeze the contract (records a hash)
    POST /api/runs/{id}:start               begin the loop (approved contracts)
    POST /api/runs/{id}:pause               pause after the active node
    POST /api/runs/{id}:resume              resume a paused run
    POST /api/runs/{id}:stop                cancel a non-terminal run
    GET  /api/runs/{id}/attempts            recorded attempts + verdicts
    POST /api/runs/{id}/gate:approve        final merge gate -> SUCCESS
    POST /api/runs/{id}/gate:reject         final merge gate -> HUMAN_REJECTED

A run cannot start until a human has approved and frozen its contract
(Principle I). Generated criteria are assigned ordered `CheckStep`s and
environment-runnable commands here (the acceptance engine only runs criteria
whose `step` is in its pipeline), so the separate engine — not the coding
agent — produces the verdict.
"""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from mergegate.acceptance.commands import run_command
from mergegate.acceptance.replay import replay_verdict
from mergegate.api.events import event_bus
from mergegate.api.store import RunRecord, store
from mergegate.auth.router import optional_current_user
from mergegate.auth.store import ConnectionError, CurrentUser, get_auth_store
from mergegate.config.providers import ProviderSelection, resolve_agent_provider
from mergegate.config.settings import load_settings
from mergegate.criteria.consistency import detect_inconsistency
from mergegate.criteria.contract import (
    ContractStateError,
    approve_contract,
    edit_draft,
)
from mergegate.criteria.generate import generate_hybrid_contract, map_repository
from mergegate.ledger.bundle import assemble_evidence_bundle
from mergegate.models import (
    AgentRole,
    Budget,
    CheckStep,
    Contract,
    CostAccounting,
    Criterion,
    NodeType,
    Policy,
    Run,
    RunStatus,
)
from mergegate.models.enums import LedgerEntryType
from mergegate.orchestrator import gates, runner
from mergegate.orchestrator.default_workflow import build_default_workflow
from mergegate.orchestrator.demo import demo_idempotency_changes, is_demo_repo
from mergegate.orchestrator.nodes import RunContext, drive_run
from mergegate.workspace.worktree import Worktree, discard_worktree

router = APIRouter()

# The interpreter that runs this process — reused as the acceptance-command
# interpreter so checks run in the current environment without a per-worktree
# dependency install (the demo-repo's deps are already importable here).
_PY = sys.executable

_OPENAPI_HEADER_CHECK = (
    f'"{_PY}" -c "from app.main import app; s=app.openapi(); '
    "params=[p['name'] for p in s['paths']['/orders']['post'].get('parameters',[])]; "
    "assert 'Idempotency-Key' in params, params\""
)

# id -> (pipeline step, runnable command) for the demo idempotency contract.
# Commands are deliberately lightweight and deterministic (no per-worktree
# `uv` install); they run against the demo-repo's own layout via the current
# interpreter, so the recorded verdict has real exit codes and steps.
_CRITERION_PLAN: dict[str, tuple[CheckStep, str]] = {
    "feature-exists": (CheckStep.BUILD, f'"{_PY}" -m compileall -q app'),
    "existing-tests": (
        CheckStep.EXISTING_TESTS,
        f'"{_PY}" -m pytest tests/test_orders.py tests/test_auth.py -q',
    ),
    "new-tests": (
        CheckStep.NEW_TESTS,
        f'"{_PY}" -m pytest tests/test_idempotency.py -q',
    ),
    "idempotency-key-required": (CheckStep.API_CONTRACT, _OPENAPI_HEADER_CHECK),
    "idempotent-order-reuse": (
        CheckStep.API_CONTRACT,
        f'"{_PY}" -m pytest tests/test_idempotency.py -q',
    ),
    "idempotency-key-conflict": (
        CheckStep.API_CONTRACT,
        f'"{_PY}" -m pytest tests/test_idempotency.py -q',
    ),
}


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


class CreateRunRequest(BaseModel):
    workflow_id: str
    objective: str
    repo_ref: str
    provider: str | None = None
    model: str | None = None
    location: str = "global"
    policy: Policy = Field(
        default_factory=lambda: Policy(
            protected_paths=["app/auth/**", "tests/acceptance/**"],
            forbidden_diff_patterns=[
                "pytest.mark.skip",
                "eslint-disable",
                "assert True",
            ],
        )
    )
    budgets: Budget


class GenerateRequest(BaseModel):
    mode: str = "hybrid"


class EditCriteriaRequest(BaseModel):
    criteria: list[Criterion]


class RejectRequest(BaseModel):
    reason: str | None = None


class ResetRepoRequest(BaseModel):
    repo_ref: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_record(run_id: str, user: CurrentUser | None = None) -> RunRecord:
    record = store.get_run(run_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"run {run_id!r} not found; active run recovery after a backend "
                "restart is not supported by the process-local v1 store"
            ),
        )
    if record.owner_id is not None and (user is None or user.id != record.owner_id):
        raise HTTPException(status_code=404, detail=f"run {run_id!r} not found")
    return record


def _run_json(run: Run, status_code: int = 200) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=run.model_dump(mode="json"))


def _specialize_criteria(contract: Contract) -> Contract:
    """Assign ordered `CheckStep`s and runnable commands to generated criteria.

    `generate.py` intentionally leaves `Criterion.step` unset; the acceptance
    engine only runs criteria whose step is in its pipeline, so this maps each
    known criterion id to a step and an environment-runnable command. Unknown
    ids are left as-is (evaluated outside the ordered pipeline).
    """
    specialized: list[Criterion] = []
    for criterion in contract.criteria:
        plan = _CRITERION_PLAN.get(criterion.id)
        if plan is None:
            specialized.append(criterion)
            continue
        step, command = plan
        specialized.append(
            criterion.model_copy(update={"step": step, "command": command})
        )
    return contract.model_copy(update={"criteria": specialized})


def _repo_subdir(repo_ref: str) -> str:
    """Path of `repo_ref` within its git top-level (``"."`` when it is the root).

    A run's worktree is a checkout of the whole git repository; when the target
    project lives in a subdirectory (e.g. ``demo-repo`` inside this mono-repo),
    the acceptance pipeline must run in that subdirectory.
    """
    resolved = run_command(["git", "rev-parse", "--show-toplevel"], cwd=repo_ref)
    if not resolved.succeeded:
        return "."
    top = Path(resolved.stdout.strip()).resolve()
    try:
        return str(Path(repo_ref).resolve().relative_to(top))
    except ValueError:
        return "."


def _resolve_repo_ref(repo_ref: str) -> str:
    """Resolve a path supplied by the UI, including the bundled demo repo.

    The backend is commonly launched from ``backend/`` while the demo fixture
    lives at the repository root. Preserve any existing caller-relative path,
    then fall back to the project-root-relative location for the built-in demo.
    """
    supplied = Path(repo_ref)
    if supplied.is_dir():
        return str(supplied.resolve())
    project_relative = Path(__file__).resolve().parents[4] / supplied
    if project_relative.is_dir():
        return str(project_relative)
    return repo_ref


def _reset_repo_tree(repo_ref: str) -> dict:
    """Restore ``repo_ref``'s working tree to a pristine ``HEAD`` baseline.

    Reverts tracked modifications *and* removes leftover untracked files (the
    part a bare ``git checkout`` misses), scoped to the target repository so a
    subsequent run starts from a genuinely red baseline. Operations are
    confined to ``repo_ref`` via ``cwd`` and a ``.`` pathspec.
    """
    resolved = _resolve_repo_ref(repo_ref)
    top = run_command(["git", "rev-parse", "--show-toplevel"], cwd=resolved)
    if not top.succeeded:
        raise HTTPException(
            status_code=400, detail=f"{repo_ref!r} is not inside a git repository"
        )
    run_command(["git", "checkout", "HEAD", "--", "."], cwd=resolved)
    removed = run_command(["git", "clean", "-fd", "."], cwd=resolved)
    status = run_command(["git", "status", "--porcelain", "."], cwd=resolved)
    return {
        "repo_ref": repo_ref,
        "clean": status.succeeded and not status.stdout.strip(),
        "removed": [
            line.removeprefix("Removing ").strip()
            for line in removed.stdout.splitlines()
            if line.strip()
        ],
        "status": status.stdout,
    }


def _select_provider(record: RunRecord) -> ProviderSelection:
    """Resolve the execution Agent's provider/model for this run.

    Explicit run config wins over the execution node and process settings.
    The bundled demo keeps its deterministic scripted fallback only when none
    of those three configuration layers selected a provider.
    """
    run = record.run
    settings = load_settings()
    execution_node = next(
        (
            node
            for node in record.workflow.nodes
            if node.type == NodeType.AGENT
            and node.config is not None
            and node.config.role == AgentRole.EXECUTION
        ),
        None,
    )
    execution_provider = (
        execution_node.config.provider
        if execution_node is not None and execution_node.config is not None
        else None
    )
    if (
        run.provider is None
        and execution_provider is None
        and is_demo_repo(run.repo_ref, run.objective)
    ):
        settings = settings.model_copy(update={"provider": "scripted"})

    return resolve_agent_provider(
        record.workflow,
        AgentRole.EXECUTION,
        settings=settings,
        provider=run.provider,
        model=run.model,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/runs")
def create_run(
    request: CreateRunRequest,
    user: CurrentUser | None = Depends(optional_current_user),
) -> JSONResponse:
    """Create a run; it sits at the contract gate with no attempts yet."""
    workflow = store.get_workflow(request.workflow_id)
    # The UI renders this built-in graph immediately, so its first run must not
    # require a separate hidden workflow-creation request.
    if workflow is None and request.workflow_id == "default-four-role-loop":
        workflow = build_default_workflow(request.workflow_id)
        store.add_workflow(workflow)
    if workflow is None:
        raise HTTPException(
            status_code=404, detail=f"workflow {request.workflow_id!r} not found"
        )

    repo_ref = request.repo_ref
    owner_id: str | None = None
    if repo_ref.startswith("github:"):
        if user is None:
            raise HTTPException(
                status_code=401, detail="Sign in with GitHub to select a repository"
            )
        try:
            repo_ref = str(
                get_auth_store().clone_repository(
                    user.id, repo_ref.removeprefix("github:")
                )
            )
        except ConnectionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        owner_id = user.id

    run = Run(
        id=f"run-{uuid4()}",
        workflow_id=request.workflow_id,
        objective=request.objective,
        repo_ref=_resolve_repo_ref(repo_ref),
        provider=request.provider,
        model=request.model,
        location=request.location.strip() or "global",
        policy=request.policy,
        status=RunStatus.AWAITING_GATE,
        budgets=request.budgets,
        current_attempt=0,
        cost=CostAccounting(),
    )
    store.add_run(run, workflow, owner_id=owner_id)
    return _run_json(run, status_code=201)


@router.post("/repo/reset")
def reset_repo(request: ResetRepoRequest) -> JSONResponse:
    """Restore a demo target repository to a pristine baseline.

    A completed run can leave changes in the base working tree; the next run
    then has no clean red baseline and stops as ``NO_PROGRESS``. This reverts
    tracked edits and clears leftover untracked files so the baseline is red
    again before the next run.
    """
    return JSONResponse(content=_reset_repo_tree(request.repo_ref))


@router.get("/runs/{run_id}")
def get_run(
    run_id: str, user: CurrentUser | None = Depends(optional_current_user)
) -> JSONResponse:
    """Return the run's status, cost, attempt counter, and mergeable ref."""
    record = _require_record(run_id, user)
    return _run_json(record.run)


@router.get("/runs/{run_id}/attempts")
def get_attempts(
    run_id: str, user: CurrentUser | None = Depends(optional_current_user)
) -> JSONResponse:
    """Return the run's recorded attempts, each with its verdict."""
    record = _require_record(run_id, user)
    return JSONResponse(
        content=[attempt.model_dump(mode="json") for attempt in record.run.attempts]
    )


@router.get("/runs/{run_id}/ledger")
def get_ledger(
    run_id: str, user: CurrentUser | None = Depends(optional_current_user)
) -> JSONResponse:
    """Return the complete durable hash-chained timeline in sequence order."""
    record = _require_record(run_id, user)
    if record.ledger is None:
        raise HTTPException(status_code=409, detail="run ledger is unavailable")
    return JSONResponse(
        content=[
            entry.model_dump(mode="json") for entry in record.ledger.read_entries()
        ]
    )


@router.post("/runs/{run_id}/event-ticket")
def create_event_ticket(
    run_id: str, user: CurrentUser | None = Depends(optional_current_user)
) -> JSONResponse:
    """Issue a short-lived ticket for a private run's SSE stream."""
    record = _require_record(run_id, user)
    if record.owner_id is None:
        return JSONResponse(content={"ticket": None})
    if user is None:
        raise HTTPException(status_code=404, detail=f"run {run_id!r} not found")
    return JSONResponse(
        content={"ticket": get_auth_store().create_event_ticket(user.id, run_id)}
    )


@router.get("/runs/{run_id}/evidence")
def get_evidence(
    run_id: str, user: CurrentUser | None = Depends(optional_current_user)
) -> JSONResponse:
    """Download a terminal bundle, preserving the live US2 proof before then."""
    record = _require_record(run_id, user)
    attempt = next(
        (item for item in reversed(record.run.attempts) if item.verdict), None
    )
    if attempt is None or attempt.red_green_evidence is None or attempt.verdict is None:
        raise HTTPException(status_code=409, detail="run has no completed evidence")
    if runner.is_terminal(record.run.status):
        if record.contract is None or record.ledger is None:
            raise HTTPException(status_code=409, detail="run evidence is incomplete")
        try:
            bundle = assemble_evidence_bundle(
                run=record.run,
                contract=record.contract,
                entries=record.ledger.read_entries(),
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return JSONResponse(
            content=bundle,
            headers={
                "Content-Disposition": 'attachment; filename="evidence-bundle.json"'
            },
        )
    return JSONResponse(
        content={
            "red_green_evidence": attempt.red_green_evidence,
            "verdict": attempt.verdict.model_dump(mode="json"),
        }
    )


@router.post("/runs/{run_id}/replay")
def replay_run(
    run_id: str, user: CurrentUser | None = Depends(optional_current_user)
) -> JSONResponse:
    """Replay the recorded verdict without starting a provider or model call."""
    record = _require_record(run_id, user)
    attempt = next(
        (item for item in reversed(record.run.attempts) if item.verdict), None
    )
    if attempt is None or attempt.verdict is None:
        raise HTTPException(
            status_code=409, detail="run has no completed verdict to replay"
        )
    try:
        replayed = replay_verdict(attempt.verdict)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if record.ledger is not None:
        record.ledger.append(
            LedgerEntryType.REPLAY,
            {
                "attempt_id": attempt.id,
                "acceptance_hash": replayed.acceptance_hash,
                "passed": replayed.passed,
                "model_calls": 0,
            },
        )
    return JSONResponse(content=replayed.model_dump(mode="json"))


@router.post("/runs/{run_id}/criteria:generate")
def generate_criteria(
    run_id: str,
    request: GenerateRequest,
    user: CurrentUser | None = Depends(optional_current_user),
) -> JSONResponse:
    """Generate a hybrid, file-grounded draft contract (not yet approved)."""
    record = _require_record(run_id, user)
    run = record.run

    repo_map = map_repository(run.repo_ref)
    contract = generate_hybrid_contract(
        objective=run.objective,
        repo_map=repo_map,
        run_id=run.id,
        contract_id=f"contract-{run.id}",
    )
    contract = _specialize_criteria(contract)
    record.contract = contract
    return JSONResponse(content=contract.model_dump(mode="json"))


@router.put("/runs/{run_id}/criteria")
def edit_criteria(
    run_id: str,
    request: EditCriteriaRequest,
    user: CurrentUser | None = Depends(optional_current_user),
) -> JSONResponse:
    """Edit / reprioritize the draft contract before approval."""
    record = _require_record(run_id, user)
    if record.contract is None:
        raise HTTPException(status_code=409, detail="no contract has been generated")

    try:
        edited = edit_draft(record.contract, request.criteria)
    except ContractStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    record.contract = edited
    return JSONResponse(content=edited.model_dump(mode="json"))


@router.post("/runs/{run_id}/criteria:approve")
def approve_criteria(
    run_id: str, user: CurrentUser | None = Depends(optional_current_user)
) -> JSONResponse:
    """Approve and freeze the draft contract, recording a frozen hash."""
    record = _require_record(run_id, user)
    if record.contract is None:
        raise HTTPException(status_code=409, detail="no contract has been generated")

    try:
        frozen = approve_contract(record.contract)
    except ContractStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    record.contract = frozen
    if record.ledger is not None:
        record.ledger.append(
            LedgerEntryType.CONTRACT,
            frozen.model_dump(mode="json"),
        )
    return JSONResponse(content=frozen.model_dump(mode="json"))


@router.post("/runs/{run_id}:start")
def start_run(
    run_id: str, user: CurrentUser | None = Depends(optional_current_user)
) -> JSONResponse:
    """Start the run's bounded loop; rejected (409) until the contract is frozen."""
    record = _require_record(run_id, user)
    run = record.run

    if record.contract is None or not record.contract.approved:
        raise HTTPException(
            status_code=409,
            detail="contract must be approved and frozen before starting",
        )
    if run.status != RunStatus.AWAITING_GATE:
        raise HTTPException(
            status_code=409, detail=f"run cannot start from status {run.status}"
        )

    def emit(event_type: str, payload: dict) -> None:
        event_bus.publish(run.id, event_type, payload)

    from mergegate.orchestrator import runner

    issue = detect_inconsistency(record.contract)
    if issue is not None:

        def emit_clarification_terminal(payload: dict) -> None:
            if record.ledger is not None:
                record.ledger.append(LedgerEntryType.TERMINAL, payload)
            emit("terminal", payload)

        runner.require_clarification(
            run,
            issue,
            on_terminal=emit_clarification_terminal,
        )
        return _run_json(run)

    # Restore the target repo to a clean, genuinely red baseline before every
    # run. A previous run can leave changes in the base working tree; without
    # this the next run has no red baseline and stops as NO_PROGRESS. Purely a
    # pre-clean step, so a failure here must not block the run.
    try:
        reset = _reset_repo_tree(run.repo_ref)
        removed = f" (removed {len(reset['removed'])})" if reset["removed"] else ""
        emit("harness_output", {"summary": f"prepared a clean baseline{removed}"})
    except Exception:  # noqa: BLE001 - best-effort baseline hygiene
        pass

    selection = _select_provider(record)
    provider = selection.provider
    subdir = _repo_subdir(run.repo_ref)

    adapter_kwargs: dict = {}
    if provider == "scripted":
        adapter_kwargs = {"changes": demo_idempotency_changes()}
    elif provider in {"anthropic", "claude-agent-sdk", "gemini", "aider", "codex"}:
        adapter_kwargs = {"model": selection.model}
        if record.owner_id is not None:
            credential = get_auth_store().provider_secret(record.owner_id, provider)
            if (
                provider in {"gemini", "anthropic", "claude-agent-sdk"}
                and not credential
            ):
                raise HTTPException(
                    status_code=400,
                    detail=f"Connect a {provider} credential before starting this run",
                )
            if credential:
                adapter_kwargs["api_key"] = credential
        if provider == "gemini":
            adapter_kwargs["location"] = run.location
        if provider in {"anthropic", "claude-agent-sdk"}:
            # Stream the agent's live actions to the run console.
            adapter_kwargs["on_event"] = emit

    context = RunContext(
        run=run,
        contract=record.contract,
        policy=run.policy,
        provider=provider,
        repo_ref=run.repo_ref,
        workspace_subdir=subdir,
        adapter_kwargs=adapter_kwargs,
        on_event=emit,
        ledger=record.ledger,
    )

    runner.transition(run, RunStatus.RUNNING)
    if record.ledger is not None:
        record.ledger.append(
            LedgerEntryType.PLAN,
            {
                "plan": json.dumps(
                    {
                        "nodes": [
                            node.model_dump(mode="json")
                            for node in record.workflow.nodes
                        ],
                        "edges": [
                            edge.model_dump(mode="json")
                            for edge in record.workflow.edges
                        ],
                    },
                    sort_keys=True,
                )
            },
        )
    thread = threading.Thread(target=drive_run, args=(context,), daemon=True)
    record.thread = thread
    thread.start()

    return _run_json(run, status_code=202)


@router.post("/runs/{run_id}:pause")
def pause_run(
    run_id: str, user: CurrentUser | None = Depends(optional_current_user)
) -> JSONResponse:
    """Request a cooperative pause after the currently active node."""
    record = _require_record(run_id, user)
    from mergegate.orchestrator import runner

    try:
        runner.transition(record.run, RunStatus.PAUSED)
    except runner.InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _run_json(record.run)


@router.post("/runs/{run_id}:resume")
def resume_run(
    run_id: str, user: CurrentUser | None = Depends(optional_current_user)
) -> JSONResponse:
    """Release a cooperatively paused run."""
    record = _require_record(run_id, user)
    from mergegate.orchestrator import runner

    if record.run.status != RunStatus.PAUSED:
        raise HTTPException(
            status_code=409,
            detail=f"cannot resume a Run in status {record.run.status}",
        )
    try:
        runner.transition(record.run, RunStatus.RUNNING)
    except runner.InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _run_json(record.run)


@router.post("/runs/{run_id}:stop")
def stop_run(
    run_id: str, user: CurrentUser | None = Depends(optional_current_user)
) -> JSONResponse:
    """Cancel a non-terminal run and discard an unmerged final attempt."""
    record = _require_record(run_id, user)
    from mergegate.orchestrator import runner

    was_awaiting_gate = record.run.status == RunStatus.AWAITING_GATE
    try:
        runner.transition(record.run, RunStatus.CANCELLED)
    except runner.InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if was_awaiting_gate and record.run.attempts:
        attempt = record.run.attempts[-1]
        discard_worktree(
            Worktree(
                path=Path(attempt.worktree_path),
                branch=attempt.branch,
                base_repo=Path(record.run.repo_ref),
                base_commit="",
            )
        )
    terminal_payload = {
        "status": RunStatus.CANCELLED.value,
        "reason": "stopped by operator",
    }
    if record.ledger is not None:
        record.ledger.append(LedgerEntryType.TERMINAL, terminal_payload)
    event_bus.publish(
        record.run.id,
        "terminal",
        terminal_payload,
    )
    return _run_json(record.run)


@router.post("/runs/{run_id}/gate:approve")
def approve_gate(
    run_id: str, user: CurrentUser | None = Depends(optional_current_user)
) -> JSONResponse:
    """Approve the final merge gate, driving the run to SUCCESS."""
    record = _require_record(run_id, user)
    try:
        gates.approve_merge(record.run)
    except gates.GateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if record.ledger is not None:
        record.ledger.append(
            LedgerEntryType.GATE,
            {"gate": "merge", "decision": "approve"},
        )
        record.ledger.append(
            LedgerEntryType.TERMINAL,
            {"status": record.run.status.value, "reason": "merge approved"},
        )
    return _run_json(record.run)


@router.post("/runs/{run_id}/gate:reject")
def reject_gate(
    run_id: str,
    request: RejectRequest,
    user: CurrentUser | None = Depends(optional_current_user),
) -> JSONResponse:
    """Reject the final merge gate, driving the run to HUMAN_REJECTED."""
    record = _require_record(run_id, user)
    try:
        gates.reject_merge(record.run, reason=request.reason)
    except gates.GateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if record.ledger is not None:
        record.ledger.append(
            LedgerEntryType.GATE,
            {
                "gate": "merge",
                "decision": "reject",
                "reason": request.reason,
            },
        )
        record.ledger.append(
            LedgerEntryType.TERMINAL,
            {"status": record.run.status.value, "reason": request.reason},
        )
    return _run_json(record.run)
