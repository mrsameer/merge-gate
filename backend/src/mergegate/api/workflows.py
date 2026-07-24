"""Workflow CRUD plus portable YAML/JSON import and export (T060)."""

from __future__ import annotations

from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel

from mergegate.api.store import store
from mergegate.models import Workflow
from mergegate.orchestrator.default_workflow import (
    TEMPLATE_FOUR_ROLE_LOOP,
    build_default_workflow,
)
from mergegate.orchestrator.serialize import (
    deserialize_workflow,
    serialize_workflow,
)

router = APIRouter()
DEFAULT_WORKFLOW_ID = "default-four-role-loop"


class CreateWorkflowRequest(BaseModel):
    """Body for `POST /api/workflows`."""

    name: str = "MergeGate default loop"
    template: str = TEMPLATE_FOUR_ROLE_LOOP


class ImportWorkflowRequest(BaseModel):
    """A human-readable workflow document and the format used to parse it."""

    format: Literal["yaml", "json"]
    content: str


def _find_workflow(workflow_id: str) -> Workflow | None:
    """Resolve saved workflows and lazily materialize the built-in template."""
    workflow = store.get_workflow(workflow_id)
    if workflow is None and workflow_id == DEFAULT_WORKFLOW_ID:
        workflow = build_default_workflow(workflow_id)
        store.add_workflow(workflow)
    return workflow


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


@router.get("/workflows/{workflow_id}")
def get_workflow(workflow_id: str) -> JSONResponse:
    """Fetch one saved workflow graph."""
    workflow = _find_workflow(workflow_id)
    if workflow is None:
        raise HTTPException(
            status_code=404, detail=f"workflow {workflow_id!r} not found"
        )
    return JSONResponse(content=workflow.model_dump(mode="json"))


@router.put("/workflows/{workflow_id}")
def update_workflow(workflow_id: str, workflow: Workflow) -> JSONResponse:
    """Replace the named workflow with a schema-validated graph."""
    if _find_workflow(workflow_id) is None:
        raise HTTPException(
            status_code=404, detail=f"workflow {workflow_id!r} not found"
        )
    if workflow.id != workflow_id:
        raise HTTPException(
            status_code=409,
            detail=(
                f"workflow body id {workflow.id!r} does not match "
                f"path id {workflow_id!r}"
            ),
        )
    store.update_workflow(workflow)
    return JSONResponse(content=workflow.model_dump(mode="json"))


@router.post("/workflows/{workflow_id}/export")
def export_workflow(
    workflow_id: str, format: Literal["yaml", "json"] = "json"
) -> PlainTextResponse:
    """Export the complete workflow as human-readable YAML or JSON."""
    workflow = _find_workflow(workflow_id)
    if workflow is None:
        raise HTTPException(
            status_code=404, detail=f"workflow {workflow_id!r} not found"
        )
    media_type = "application/yaml" if format == "yaml" else "application/json"
    return PlainTextResponse(
        content=serialize_workflow(workflow, format),
        media_type=media_type,
        headers={
            "Content-Disposition": (f'attachment; filename="{workflow.id}.{format}"')
        },
    )


@router.post("/workflows/import")
def import_workflow(request: ImportWorkflowRequest) -> JSONResponse:
    """Validate, store, and return a portable workflow document."""
    try:
        workflow = deserialize_workflow(request.content, request.format)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=422, detail=f"invalid workflow configuration: {exc}"
        ) from exc
    store.add_workflow(workflow)
    return JSONResponse(status_code=201, content=workflow.model_dump(mode="json"))
