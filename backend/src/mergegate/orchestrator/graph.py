"""Workflow config loader (YAML/JSON) and LangGraph graph assembly (T012,
data-model.md § Workflow, FR-028/FR-028a).

`load_workflow_config` turns human-authored YAML or JSON into a validated
`Workflow`, re-using `Workflow`'s own schema validation (T007) so a malformed
config fails here rather than mid-run. `build_graph` then assembles that
`Workflow` into a LangGraph `StateGraph`: one graph node per workflow `Node`,
wired by the workflow's `Edge`s — a single outgoing edge becomes a plain
edge, and edges that share a source but carry different `path` labels become
a conditional edge keyed by `GraphState.path`. `Success` and `Stop` nodes are
always terminal, per data-model.md's "≥1 Success and ≥1 Stop" invariant.

Node execution here is a placeholder pass-through: deciding *which* path a
Validator/Decision node takes is business logic that belongs to the runner
(T013) and later harness/acceptance tasks, not to structural graph assembly.
"""

from collections import defaultdict
from pathlib import Path
from typing import Any, TypedDict

import yaml
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from mergegate.models import Edge, EdgePath, NodeType, Workflow


class GraphState(TypedDict, total=False):
    """Shared state threaded through one workflow run.

    `path` is the edge label the most recently run node wants to follow
    (`default`, `success`, or `failure`); conditional routers read it to pick
    the next node. `node_results` accumulates each node's placeholder output,
    keyed by node id.
    """

    objective: str
    path: str
    node_results: dict[str, Any]


def load_workflow_config(source: str | Path) -> Workflow:
    """Parse a workflow config into a validated `Workflow` (FR-028).

    A `Path` is read as a file; a `str` is parsed directly as config text.
    YAML is a superset of JSON, so `yaml.safe_load` handles both formats
    without needing to sniff the source's shape.
    """
    text = source.read_text() if isinstance(source, Path) else source
    data = yaml.safe_load(text)
    return Workflow.model_validate(data)


def build_graph(
    workflow: Workflow, *, checkpointer: BaseCheckpointSaver | None = None
) -> CompiledStateGraph:
    """Assemble `workflow` into a compiled LangGraph `StateGraph`.

    `checkpointer` wires in durable, replayable execution (T013): with one
    attached, the compiled graph persists state after every superstep so a
    `Runner` can pause and later resume a run from its last checkpoint
    instead of restarting it.
    """
    graph = StateGraph(GraphState)
    for node in workflow.nodes:
        graph.add_node(node.id, _passthrough_action(node.id))

    input_node = next(n for n in workflow.nodes if n.type == NodeType.INPUT)
    graph.set_entry_point(input_node.id)

    edges_by_source: dict[str, list[Edge]] = defaultdict(list)
    for edge in workflow.edges:
        edges_by_source[edge.source].append(edge)

    for node in workflow.nodes:
        if node.type in (NodeType.SUCCESS, NodeType.STOP):
            graph.add_edge(node.id, END)
            continue
        _wire_outgoing_edges(graph, node.id, edges_by_source.get(node.id, []))

    return graph.compile(checkpointer=checkpointer)


def _wire_outgoing_edges(
    graph: StateGraph, source_id: str, outgoing: list[Edge]
) -> None:
    if not outgoing:
        graph.add_edge(source_id, END)
    elif len(outgoing) == 1:
        graph.add_edge(source_id, outgoing[0].target)
    else:
        graph.add_conditional_edges(
            source_id,
            _path_router,
            {edge.path.value: edge.target for edge in outgoing},
        )


def _path_router(state: GraphState) -> str:
    return state.get("path", EdgePath.DEFAULT.value)


def _passthrough_action(node_id: str):
    def action(state: GraphState) -> dict[str, Any]:
        results = dict(state.get("node_results", {}))
        results[node_id] = "ran"
        return {"node_results": results}

    return action
