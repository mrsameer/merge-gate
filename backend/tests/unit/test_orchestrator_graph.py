"""Workflow config loader + LangGraph graph assembly tests for T012.

Encodes two behaviors from `tasks.md`'s T012 and data-model.md § Workflow:
`load_workflow_config` turns YAML or JSON (file or text) into the same
validated `Workflow` that T007 already guards (FR-028: paths are data, not
hardcoded), and `build_graph` assembles that `Workflow` into a LangGraph
`StateGraph` whose entry point, plain edges, and conditional (success/
failure) edges mirror the workflow's node/edge structure exactly.
"""

import json
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from mergegate.orchestrator.graph import build_graph, load_workflow_config

_LOOP_CONFIG: dict = {
    "id": "wf-loop",
    "name": "Default Loop",
    "nodes": [
        {"id": "input", "type": "Input", "name": "Objective"},
        {
            "id": "planning",
            "type": "Agent",
            "name": "Planning",
            "config": {"role": "planning"},
        },
        {
            "id": "execution",
            "type": "Agent",
            "name": "Execution",
            "config": {"role": "execution"},
        },
        {"id": "validation", "type": "Validator", "name": "Validation"},
        {"id": "success", "type": "Success", "name": "Success"},
        {"id": "stop", "type": "Stop", "name": "Stop"},
    ],
    "edges": [
        {"source": "input", "target": "planning"},
        {"source": "planning", "target": "execution"},
        {"source": "execution", "target": "validation"},
        {"source": "validation", "target": "success", "path": "success"},
        {"source": "validation", "target": "stop", "path": "failure"},
    ],
}

_RETRY_LOOP_CONFIG: dict = {
    **_LOOP_CONFIG,
    "edges": [
        {"source": "input", "target": "planning"},
        {"source": "planning", "target": "execution"},
        {"source": "execution", "target": "validation"},
        {"source": "validation", "target": "success", "path": "success"},
        {"source": "validation", "target": "planning", "path": "failure"},
    ],
}


def test_load_workflow_config_parses_yaml_text() -> None:
    workflow = load_workflow_config(yaml.safe_dump(_LOOP_CONFIG))
    assert workflow.id == "wf-loop"
    assert len(workflow.nodes) == 6


def test_load_workflow_config_parses_json_text() -> None:
    workflow = load_workflow_config(json.dumps(_LOOP_CONFIG))
    assert workflow.id == "wf-loop"
    assert len(workflow.edges) == 5


def test_load_workflow_config_reads_yaml_file(tmp_path: Path) -> None:
    config_path = tmp_path / "workflow.yaml"
    config_path.write_text(yaml.safe_dump(_LOOP_CONFIG))
    workflow = load_workflow_config(config_path)
    assert workflow.id == "wf-loop"


def test_load_workflow_config_reads_json_file(tmp_path: Path) -> None:
    config_path = tmp_path / "workflow.json"
    config_path.write_text(json.dumps(_LOOP_CONFIG))
    workflow = load_workflow_config(config_path)
    assert workflow.id == "wf-loop"


def test_load_workflow_config_yaml_and_json_produce_identical_workflow() -> None:
    from_yaml = load_workflow_config(yaml.safe_dump(_LOOP_CONFIG))
    from_json = load_workflow_config(json.dumps(_LOOP_CONFIG))
    assert from_yaml == from_json


def test_load_workflow_config_rejects_schema_violation() -> None:
    too_few_nodes = {**_LOOP_CONFIG, "nodes": _LOOP_CONFIG["nodes"][:2]}
    with pytest.raises(ValidationError):
        load_workflow_config(json.dumps(too_few_nodes))


def test_build_graph_sets_entry_point_to_input_node() -> None:
    workflow = load_workflow_config(json.dumps(_LOOP_CONFIG))
    compiled = build_graph(workflow)
    edges = compiled.get_graph().edges
    assert any(e.source == "__start__" and e.target == "input" for e in edges)


def test_build_graph_wires_single_default_edge_as_plain_edge() -> None:
    workflow = load_workflow_config(json.dumps(_LOOP_CONFIG))
    compiled = build_graph(workflow)
    edges = compiled.get_graph().edges
    assert any(
        e.source == "planning" and e.target == "execution" and not e.conditional
        for e in edges
    )


def test_build_graph_wires_branching_edges_as_conditional() -> None:
    workflow = load_workflow_config(json.dumps(_LOOP_CONFIG))
    compiled = build_graph(workflow)
    edges = {(e.source, e.target): e for e in compiled.get_graph().edges}
    assert edges[("validation", "success")].conditional
    assert edges[("validation", "stop")].conditional


def test_build_graph_terminal_nodes_always_route_to_end() -> None:
    workflow = load_workflow_config(json.dumps(_LOOP_CONFIG))
    compiled = build_graph(workflow)
    edges = compiled.get_graph().edges
    assert any(e.source == "success" and e.target == "__end__" for e in edges)
    assert any(e.source == "stop" and e.target == "__end__" for e in edges)


def test_build_graph_invoke_follows_success_path_to_success_node() -> None:
    workflow = load_workflow_config(json.dumps(_LOOP_CONFIG))
    compiled = build_graph(workflow)
    result = compiled.invoke({"path": "success"})
    assert result["node_results"]["success"] == "ran"
    assert "stop" not in result["node_results"]


def test_build_graph_invoke_follows_failure_path_to_stop_node() -> None:
    workflow = load_workflow_config(json.dumps(_LOOP_CONFIG))
    compiled = build_graph(workflow)
    result = compiled.invoke({"path": "failure"})
    assert result["node_results"]["stop"] == "ran"
    assert "success" not in result["node_results"]


def test_build_graph_supports_retry_cycle_back_to_earlier_node() -> None:
    """Failure paths may loop back to an earlier node (e.g. re-planning);
    assembly must accept the cycle without erroring (FR-031's retry limit is
    the runner's concern (T013), not graph assembly's).
    """
    workflow = load_workflow_config(json.dumps(_RETRY_LOOP_CONFIG))
    compiled = build_graph(workflow)
    edges = {(e.source, e.target): e for e in compiled.get_graph().edges}
    assert edges[("validation", "planning")].conditional
