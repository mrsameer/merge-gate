"""T028 — the Runs REST surface (create / status / criteria / start / gate).

Implements the contract-before-code lifecycle promised by
`contracts/control-plane-api.md`:

    POST /api/runs                          create a run (at the contract gate)
    GET  /api/runs/{id}                     run status incl. cost + attempts
    POST /api/runs/{id}/criteria:generate   hybrid criteria grounded in files
    PUT  /api/runs/{id}/criteria            edit/prioritize (pre-approval only)
    POST /api/runs/{id}/criteria:approve    freeze the contract (records a hash)
    POST /api/runs/{id}:start               begin the loop (approved contracts)
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

import os
import sys
import threading
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from mergegate.acceptance.commands import run_command
from mergegate.acceptance.replay import replay_verdict
from mergegate.api.events import event_bus
from mergegate.api.store import RunRecord, store
from mergegate.config.settings import load_settings
from mergegate.criteria.consistency import detect_inconsistency
from mergegate.criteria.contract import (
    ContractStateError,
    approve_contract,
    edit_draft,
)
from mergegate.criteria.generate import generate_hybrid_contract, map_repository
from mergegate.models import (
    Budget,
    CheckStep,
    Contract,
    CostAccounting,
    Criterion,
    Run,
    RunStatus,
)
from mergegate.orchestrator import gates
from mergegate.orchestrator.default_workflow import build_default_workflow
from mergegate.orchestrator.demo import demo_idempotency_changes, is_demo_repo
from mergegate.orchestrator.nodes import RunContext, drive_run

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
        f'"{_PY}" -m pytest tests/test_idempotency.py -q -k same_key_same_body',
    ),
    "idempotency-key-conflict": (
        CheckStep.API_CONTRACT,
        f'"{_PY}" -m pytest tests/test_idempotency.py -q -k different_body',
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
    budgets: Budget


class GenerateRequest(BaseModel):
    mode: str = "hybrid"


class EditCriteriaRequest(BaseModel):
    criteria: list[Criterion]


class RejectRequest(BaseModel):
    reason: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_record(run_id: str) -> RunRecord:
    record = store.get_run(run_id)
    if record is None:
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


def _select_provider(run: Run) -> str:
    """Pick the harness provider for this run.

    An explicit ``MERGEGATE_PROVIDER`` env var always wins; otherwise the demo
    idempotency scenario defaults to the deterministic ``scripted`` provider so
    the happy path runs offline with no API key, and everything else falls back
    to the configured default provider.
    """
    if run.provider:
        return run.provider
    env_provider = os.environ.get("MERGEGATE_PROVIDER")
    if env_provider:
        return env_provider
    if is_demo_repo(run.repo_ref, run.objective):
        return "scripted"
    return load_settings().provider


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/runs")
def create_run(request: CreateRunRequest) -> JSONResponse:
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

    run = Run(
        id=f"run-{uuid4()}",
        workflow_id=request.workflow_id,
        objective=request.objective,
        repo_ref=_resolve_repo_ref(request.repo_ref),
        provider=request.provider,
        model=request.model,
        status=RunStatus.AWAITING_GATE,
        budgets=request.budgets,
        current_attempt=0,
        cost=CostAccounting(),
    )
    store.add_run(run, workflow)
    return _run_json(run, status_code=201)


@router.get("/runs/{run_id}")
def get_run(run_id: str) -> JSONResponse:
    """Return the run's status, cost, attempt counter, and mergeable ref."""
    record = _require_record(run_id)
    return _run_json(record.run)


@router.get("/runs/{run_id}/attempts")
def get_attempts(run_id: str) -> JSONResponse:
    """Return the run's recorded attempts, each with its verdict."""
    record = _require_record(run_id)
    return JSONResponse(
        content=[attempt.model_dump(mode="json") for attempt in record.run.attempts]
    )


@router.get("/runs/{run_id}/evidence")
def get_evidence(run_id: str) -> JSONResponse:
    """Return the latest red→green proof and deterministic verdict."""
    record = _require_record(run_id)
    attempt = next(
        (item for item in reversed(record.run.attempts) if item.verdict), None
    )
    if attempt is None or attempt.red_green_evidence is None or attempt.verdict is None:
        raise HTTPException(status_code=409, detail="run has no completed evidence")
    return JSONResponse(
        content={
            "red_green_evidence": attempt.red_green_evidence,
            "verdict": attempt.verdict.model_dump(mode="json"),
        }
    )


@router.post("/runs/{run_id}/replay")
def replay_run(run_id: str) -> JSONResponse:
    """Replay the recorded verdict without starting a provider or model call."""
    record = _require_record(run_id)
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
    return JSONResponse(content=replayed.model_dump(mode="json"))


@router.post("/runs/{run_id}/criteria:generate")
def generate_criteria(run_id: str, request: GenerateRequest) -> JSONResponse:
    """Generate a hybrid, file-grounded draft contract (not yet approved)."""
    record = _require_record(run_id)
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
def edit_criteria(run_id: str, request: EditCriteriaRequest) -> JSONResponse:
    """Edit / reprioritize the draft contract before approval."""
    record = _require_record(run_id)
    if record.contract is None:
        raise HTTPException(status_code=409, detail="no contract has been generated")

    try:
        edited = edit_draft(record.contract, request.criteria)
    except ContractStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    record.contract = edited
    return JSONResponse(content=edited.model_dump(mode="json"))


@router.post("/runs/{run_id}/criteria:approve")
def approve_criteria(run_id: str) -> JSONResponse:
    """Approve and freeze the draft contract, recording a frozen hash."""
    record = _require_record(run_id)
    if record.contract is None:
        raise HTTPException(status_code=409, detail="no contract has been generated")

    try:
        frozen = approve_contract(record.contract)
    except ContractStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    record.contract = frozen
    return JSONResponse(content=frozen.model_dump(mode="json"))


@router.post("/runs/{run_id}:start")
def start_run(run_id: str) -> JSONResponse:
    """Start the run's bounded loop; rejected (409) until the contract is frozen."""
    record = _require_record(run_id)
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
        runner.require_clarification(
            run,
            issue,
            on_terminal=lambda payload: emit("terminal", payload),
        )
        return _run_json(run)

    provider = _select_provider(run)
    subdir = _repo_subdir(run.repo_ref)

    adapter_kwargs: dict = {}
    if provider == "scripted":
        prefix = subdir if subdir != "." else ""
        adapter_kwargs = {"changes": demo_idempotency_changes(prefix=prefix)}
    elif provider in {"anthropic", "gemini"} and run.model:
        adapter_kwargs = {"model": run.model}

    context = RunContext(
        run=run,
        contract=record.contract,
        provider=provider,
        repo_ref=run.repo_ref,
        workspace_subdir=subdir,
        adapter_kwargs=adapter_kwargs,
        on_event=emit,
    )

    runner.transition(run, RunStatus.RUNNING)
    thread = threading.Thread(target=drive_run, args=(context,), daemon=True)
    record.thread = thread
    thread.start()

    return _run_json(run, status_code=202)


@router.post("/runs/{run_id}/gate:approve")
def approve_gate(run_id: str) -> JSONResponse:
    """Approve the final merge gate, driving the run to SUCCESS."""
    record = _require_record(run_id)
    try:
        gates.approve_merge(record.run)
    except gates.GateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _run_json(record.run)


@router.post("/runs/{run_id}/gate:reject")
def reject_gate(run_id: str, request: RejectRequest) -> JSONResponse:
    """Reject the final merge gate, driving the run to HUMAN_REJECTED."""
    record = _require_record(run_id)
    try:
        gates.reject_merge(record.run, reason=request.reason)
    except gates.GateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _run_json(record.run)
