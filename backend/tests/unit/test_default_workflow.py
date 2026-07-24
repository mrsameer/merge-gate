"""Unit tests for the default four-role-loop workflow builder."""

from __future__ import annotations

from mergegate.models import NodeType
from mergegate.orchestrator.default_workflow import build_default_workflow


def test_default_workflow_has_four_roles_and_both_gates() -> None:
    workflow = build_default_workflow("wf-1")

    node_ids = {node.id for node in workflow.nodes}
    assert {
        "input",
        "success-criteria",
        "contract-gate",
        "planning",
        "execution",
        "validator",
        "decision",
        "merge-gate",
        "success",
        "stop",
    } <= node_ids

    gates = [n for n in workflow.nodes if n.type == NodeType.HUMAN_GATE]
    assert {n.id for n in gates} == {"contract-gate", "merge-gate"}

    assert any(n.type == NodeType.SUCCESS for n in workflow.nodes)
    assert any(n.type == NodeType.STOP for n in workflow.nodes)


def test_default_workflow_has_retry_edge_back_to_planning() -> None:
    workflow = build_default_workflow("wf-2")
    retry = [
        e for e in workflow.edges if e.source == "decision" and e.target == "planning"
    ]
    assert retry, "decision must have a retry edge back to planning"
