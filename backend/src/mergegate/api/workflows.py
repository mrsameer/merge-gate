"""T028 — `POST /api/workflows`: create a workflow from a template.

For US1 the only template is the four-role loop (`build_default_workflow`);
the endpoint returns the full serialized `Workflow` so the frontend canvas can
render it and later runs can reference it by id.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from mergegate.api.store import store
from mergegate.orchestrator.default_workflow import (
    TEMPLATE_FOUR_ROLE_LOOP,
    build_default_workflow,
)

router = APIRouter()


class CreateWorkflowRequest(BaseModel):
    """Body for `POST /api/workflows`."""

    name: str = "MergeGate default loop"
    template: str = TEMPLATE_FOUR_ROLE_LOOP


@router.post("/workflows")
def create_workflow(request: CreateWorkflowRequest) -> JSONResponse:
    """Create a workflow from `template` and return it (201)."""
    if request.template != TEMPLATE_FOUR_ROLE_LOOP:
        raise HTTPException(
            status_code=400,
            detail=f"unknown workflow template {request.template!r}",
        )

    workflow = build_default_workflow(f"wf-{uuid4()}", name=request.name)
    store.add_workflow(workflow)
    return JSONResponse(status_code=201, content=workflow.model_dump(mode="json"))
