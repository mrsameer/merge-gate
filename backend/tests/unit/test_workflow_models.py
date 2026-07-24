"""Workflow/Node/Edge model tests for T007.

Encodes the node-graph shape from `data-model.md` § Workflow/Node/Edge and the
wire format in `contracts/workflow.schema.json`, so the models stay faithful to
both: valid graphs must construct and re-import identically (FR-028/FR-028a/
SC-014), and graphs that violate the schema (too few nodes, unknown enum
values, unexpected properties) must be rejected at construction time rather
than silently accepted.

Invalid-value tests deliberately pass strings that aren't valid enum members
to prove runtime validation rejects them; `cast` tells pyright to trust that on
those lines, since the whole point is to check what pydantic does with input
the type checker would otherwise never allow through.
"""

import json
from pathlib import Path
from typing import cast

import jsonschema
import pytest
from pydantic import ValidationError

from mergegate.models import (
    AgentRole,
    Edge,
    EdgePath,
    Node,
    NodeConfig,
    NodeType,
    Workflow,
)

SCHEMA_PATH = (
    Path(__file__).resolve().parents[3]
    / "specs"
    / "001-mergegate-control-plane"
    / "contracts"
    / "workflow.schema.json"
)


def _minimal_workflow() -> Workflow:
    return Workflow(
        id="wf-1",
        name="Default Loop",
        nodes=[
            Node(id="input", type=NodeType.INPUT, name="Objective"),
            Node(
                id="execution",
                type=NodeType.AGENT,
                name="Execution",
                config=NodeConfig(role=AgentRole.EXECUTION, provider="cursor"),
            ),
            Node(id="success", type=NodeType.SUCCESS, name="Success"),
            Node(id="stop", type=NodeType.STOP, name="Stop"),
        ],
        edges=[
            Edge(source="input", target="execution"),
            Edge(source="execution", target="success", path=EdgePath.SUCCESS),
            Edge(source="execution", target="stop", path=EdgePath.FAILURE),
        ],
    )


def test_minimal_workflow_constructs_with_expected_shape() -> None:
    workflow = _minimal_workflow()
    assert len(workflow.nodes) == 4
    assert workflow.nodes[0].type == NodeType.INPUT
    assert workflow.edges[1].path == EdgePath.SUCCESS


def test_workflow_export_conforms_to_contracts_schema_file() -> None:
    """The exported dict must validate against the actual repo schema file,
    independent of the model's own internal validator, so drift in either
    the model or the schema shows up here.
    """
    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.validate(_minimal_workflow().to_schema_dict(), schema)


def test_workflow_round_trip_import_export_is_identical() -> None:
    original = _minimal_workflow()
    reimported = Workflow.model_validate(original.to_schema_dict())
    assert reimported == original


def test_workflow_rejects_fewer_than_three_nodes() -> None:
    with pytest.raises(ValidationError, match="minItems|too_short|3"):
        Workflow(
            id="wf-2",
            name="Too Small",
            nodes=[
                Node(id="input", type=NodeType.INPUT, name="Objective"),
                Node(id="stop", type=NodeType.STOP, name="Stop"),
            ],
        )


def test_workflow_rejects_unexpected_top_level_property() -> None:
    data = _minimal_workflow().to_schema_dict()
    data["unexpected_field"] = True
    with pytest.raises(ValidationError):
        Workflow.model_validate(data)


def test_node_type_rejects_unknown_value() -> None:
    with pytest.raises(ValidationError):
        Node(id="n1", type=cast(NodeType, "NotARealType"), name="Bogus")


def test_edge_path_defaults_to_default() -> None:
    edge = Edge(source="a", target="b")
    assert edge.path == EdgePath.DEFAULT


def test_edge_rejects_unknown_path_value() -> None:
    with pytest.raises(ValidationError):
        Edge(source="a", target="b", path=cast(EdgePath, "loopback"))


def test_node_config_only_carries_declared_fields() -> None:
    config = NodeConfig(
        role=AgentRole.VALIDATION,
        command="pytest -q",
        timeout_s=60,
        retry_limit=2,
    )
    assert config.role == AgentRole.VALIDATION
    assert config.instructions is None


def test_node_config_rejects_unexpected_property() -> None:
    with pytest.raises(ValidationError):
        NodeConfig.model_validate({"role": "execution", "not_a_field": "x"})
