"""Workflow/Node/Edge models with schema validation against
`contracts/workflow.schema.json` (data-model.md § Workflow/Node/Edge,
FR-026a/FR-027/FR-028/FR-028a).

Every property here mirrors the JSON schema exactly (including
`additionalProperties: false`, enforced via `extra="forbid"`), and the
constructed `Workflow` re-validates its exported form against the schema
file itself so drift between the two is caught immediately rather than at
import time in the orchestrator (T012).
"""

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from pydantic import BaseModel, ConfigDict, Field, model_validator

from mergegate.models.enums import AgentRole, EdgePath, NodeType

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[4]
    / "specs"
    / "001-mergegate-control-plane"
    / "contracts"
    / "workflow.schema.json"
)
_WORKFLOW_SCHEMA_VALIDATOR = Draft202012Validator(json.loads(_SCHEMA_PATH.read_text()))


class NodeConfig(BaseModel):
    """Per-node settings; only fields relevant to the node's type are honored
    (FR-027/FR-031).
    """

    model_config = ConfigDict(extra="forbid")

    role: AgentRole | None = None
    instructions: str | None = None
    provider: str | None = None
    model: str | None = None
    tools: list[str] | None = None
    command: str | None = None
    timeout_s: int | None = None
    criteria_ref: str | None = None
    retry_limit: int | None = None
    completion_condition: str | None = None
    success_path: str | None = None
    failure_path: str | None = None


class Node(BaseModel):
    """A single node in the workflow graph."""

    model_config = ConfigDict(extra="forbid")

    id: str
    type: NodeType
    name: str
    config: NodeConfig | None = None


class Edge(BaseModel):
    """A directed connection between two nodes, carrying a path label
    (FR-026a).
    """

    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    source: str
    target: str
    path: EdgePath = EdgePath.DEFAULT


class WorkflowBudgets(BaseModel):
    """Optional attempt/time/model-call ceilings carried by the workflow
    itself.
    """

    model_config = ConfigDict(extra="forbid")

    max_attempts: int | None = None
    max_wall_clock_s: int | None = None
    max_model_calls: int | None = None


class Workflow(BaseModel):
    """The typed-node graph; its default form is the four-role loop.

    Serializable to YAML/JSON and re-importable to an identical structure
    (FR-028, FR-028a, SC-014).
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    version: str | None = None
    nodes: list[Node]
    edges: list[Edge] = Field(default_factory=list)
    budgets: WorkflowBudgets | None = None

    def to_schema_dict(self) -> dict[str, Any]:
        """Serialize to the exact shape validated by `workflow.schema.json`."""
        return self.model_dump(mode="json", exclude_none=True)

    @model_validator(mode="after")
    def _validate_against_workflow_schema(self) -> "Workflow":
        try:
            _WORKFLOW_SCHEMA_VALIDATOR.validate(self.to_schema_dict())
        except JsonSchemaValidationError as exc:
            raise ValueError(
                f"workflow does not conform to workflow.schema.json: {exc.message}"
            ) from exc
        return self
