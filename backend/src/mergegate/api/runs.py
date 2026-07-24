from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from mergegate.config.settings import get_settings
from mergegate.ledger.store import RunStore
from mergegate.models import Budget, Run, RunStatus
from mergegate.orchestrator.runner import build_orchestrator


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorEnvelope(BaseModel):
    error: ErrorBody


class CreateRunRequest(BaseModel):
    workflow_id: str
    objective: str
    repo_ref: str
    budgets: Budget | None = None


def create_app() -> FastAPI:
    settings = get_settings()
    store = RunStore(settings.data_dir / "runs")
    orchestrator = build_orchestrator(store)
    app = FastAPI(title="MergeGate Control Plane")

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {"code": str(exc.status_code), "message": str(exc.detail)}
            },
        )

    @app.post("/api/runs", status_code=201)
    def create_run(body: CreateRunRequest) -> Run:
        run = Run(
            id=str(uuid4()),
            workflow_id=body.workflow_id,
            objective=body.objective,
            repo_ref=body.repo_ref,
            budgets=body.budgets or Budget(),
            status=RunStatus.AWAITING_GATE,
            current_attempt=0,
        )
        store.save(run)
        store.ledger.append(run.id, "objective", {"objective": run.objective})
        return run

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> Run:
        run = store.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="run not found")
        return run

    @app.post("/api/runs/{run_id}/criteria:generate")
    def generate_criteria(run_id: str) -> dict:
        run = store.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="run not found")
        run = orchestrator.generate_criteria(run)
        assert run.contract is not None
        return {"contract": run.contract}

    @app.put("/api/runs/{run_id}/criteria")
    def edit_criteria(run_id: str, body: dict) -> dict:
        run = store.get(run_id)
        if run is None or run.contract is None:
            raise HTTPException(status_code=404, detail="run not found")
        criteria = body.get("criteria")
        if criteria is not None:
            from mergegate.models import Criterion

            run.contract.criteria = [Criterion.model_validate(c) for c in criteria]
            run.contract.approved = False
            run.contract.frozen_hash = None
            store.save(run)
        return {"contract": run.contract}

    @app.post("/api/runs/{run_id}/criteria:approve")
    def approve_criteria(run_id: str) -> dict:
        run = store.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="run not found")
        run = orchestrator.approve_contract(run)
        return {"contract": run.contract}

    @app.post("/api/runs/{run_id}:start")
    def start_run(run_id: str) -> Run:
        run = store.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="run not found")
        if run.contract is None or not run.contract.approved:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": {
                        "code": "CONTRACT_NOT_APPROVED",
                        "message": "Contract must be approved before start",
                    }
                },
            )
        return orchestrator.start_run(run)

    @app.post("/api/runs/{run_id}/gate:approve")
    def approve_gate(run_id: str) -> Run:
        run = store.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="run not found")
        return orchestrator.approve_final_gate(run)

    return app


app = create_app()
