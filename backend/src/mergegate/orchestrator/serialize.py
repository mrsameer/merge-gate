"""Human-readable workflow serialization for US7 import/export.

The serialized document is the workflow itself, rather than an API-specific
envelope, so the graph remains portable and can be assembled directly by
``load_workflow_config``. Both formats round-trip through the same validated
``Workflow`` model.
"""

from __future__ import annotations

import json
from typing import Any, Literal, cast

import yaml

from mergegate.models import Workflow

WorkflowFormat = Literal["json", "yaml"]


def _format(value: str) -> WorkflowFormat:
    normalized = value.lower()
    if normalized not in {"json", "yaml"}:
        raise ValueError(f"unsupported workflow format {value!r}")
    return cast(WorkflowFormat, normalized)


def serialize_workflow(workflow: Workflow, format: str) -> str:
    """Serialize ``workflow`` deterministically as indented JSON or YAML."""
    data = workflow.to_schema_dict()
    if _format(format) == "json":
        return f"{json.dumps(data, indent=2, sort_keys=True)}\n"
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


def deserialize_workflow(content: str, format: str) -> Workflow:
    """Parse and schema-validate a serialized workflow."""
    parsed: Any
    if _format(format) == "json":
        parsed = json.loads(content)
    else:
        try:
            parsed = yaml.safe_load(content)
        except yaml.YAMLError as exc:
            raise ValueError(f"invalid YAML: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("workflow configuration must contain an object")
    return Workflow.model_validate(parsed)
