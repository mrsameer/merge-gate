from __future__ import annotations

from mergegate.models import AgentRole, Edge, Node, NodeConfig, NodeType, Workflow


def default_four_role_loop(workflow_id: str) -> Workflow:
    nodes = [
        Node(id="input", type=NodeType.INPUT, name="Input"),
        Node(
            id="success_criteria",
            type=NodeType.AGENT,
            name="Success Criteria",
            config=NodeConfig(role=AgentRole.SUCCESS_CRITERIA),
        ),
        Node(id="contract_gate", type=NodeType.HUMAN_GATE, name="Contract Gate"),
        Node(
            id="planning",
            type=NodeType.AGENT,
            name="Planning",
            config=NodeConfig(role=AgentRole.PLANNING),
        ),
        Node(
            id="execution",
            type=NodeType.AGENT,
            name="Execution",
            config=NodeConfig(role=AgentRole.EXECUTION),
        ),
        Node(
            id="validation",
            type=NodeType.VALIDATOR,
            name="Validation",
            config=NodeConfig(role=AgentRole.VALIDATION),
        ),
        Node(id="final_gate", type=NodeType.HUMAN_GATE, name="Final Gate"),
        Node(id="success", type=NodeType.SUCCESS, name="Success"),
        Node(id="stop", type=NodeType.STOP, name="Stop"),
    ]
    edges = [
        Edge(source="input", target="success_criteria"),
        Edge(source="success_criteria", target="contract_gate"),
        Edge(source="contract_gate", target="planning"),
        Edge(source="planning", target="execution"),
        Edge(source="execution", target="validation"),
        Edge(source="validation", target="final_gate", path="success"),
        Edge(source="validation", target="planning", path="failure"),
        Edge(source="final_gate", target="success", path="success"),
        Edge(source="final_gate", target="stop", path="failure"),
    ]
    return Workflow(
        id=workflow_id, name="Default four-role loop", nodes=nodes, edges=edges
    )
