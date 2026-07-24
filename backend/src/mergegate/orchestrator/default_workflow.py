"""The default four-role loop workflow (T028 support).

Builds the canonical MergeGate workflow that the frontend canvas
(`frontend/src/canvas/defaultWorkflow.ts`) renders and that US1's happy path
runs:

    Input -> Success Criteria -> Contract Gate -> Planning -> Execution
    -> Validator -> Decision -> (Merge Gate -> Success) | Stop

with a retry edge from Decision back to Planning while attempts remain
(FR-012). Two human gates bracket the code-writing loop: ``contract-gate`` is
the pre-start contract approval (Principle I: contract before code), and
``merge-gate`` is the final human approval before a passing attempt is declared
merged (T029).

The constructed :class:`~mergegate.models.Workflow` re-validates itself against
`contracts/workflow.schema.json`, so this function is also the guarantee that
the default loop stays schema-conformant.
"""

from __future__ import annotations

from mergegate.models import AgentRole, Edge, EdgePath, Node, NodeConfig, NodeType
from mergegate.models.workflow import Workflow

TEMPLATE_FOUR_ROLE_LOOP = "four_role_loop"


def build_default_workflow(
    workflow_id: str, name: str = "MergeGate default loop"
) -> Workflow:
    """Return the four-role-loop :class:`Workflow` with both human gates."""
    nodes = [
        Node(id="input", type=NodeType.INPUT, name="Input"),
        Node(
            id="success-criteria",
            type=NodeType.AGENT,
            name="Success Criteria",
            config=NodeConfig(role=AgentRole.SUCCESS_CRITERIA),
        ),
        Node(id="contract-gate", type=NodeType.HUMAN_GATE, name="Contract Gate"),
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
            id="validator",
            type=NodeType.VALIDATOR,
            name="Validator",
            config=NodeConfig(role=AgentRole.VALIDATION),
        ),
        Node(id="decision", type=NodeType.DECISION, name="Decision"),
        Node(id="merge-gate", type=NodeType.HUMAN_GATE, name="Merge Gate"),
        Node(id="success", type=NodeType.SUCCESS, name="Success"),
        Node(id="stop", type=NodeType.STOP, name="Stop"),
    ]

    edges = [
        Edge(id="e-input-criteria", source="input", target="success-criteria"),
        Edge(id="e-criteria-gate", source="success-criteria", target="contract-gate"),
        Edge(
            id="e-gate-planning",
            source="contract-gate",
            target="planning",
            path=EdgePath.SUCCESS,
        ),
        Edge(id="e-planning-execution", source="planning", target="execution"),
        Edge(id="e-execution-validator", source="execution", target="validator"),
        Edge(id="e-validator-decision", source="validator", target="decision"),
        Edge(
            id="e-decision-merge",
            source="decision",
            target="merge-gate",
            path=EdgePath.SUCCESS,
        ),
        Edge(
            id="e-decision-retry",
            source="decision",
            target="planning",
            path=EdgePath.FAILURE,
        ),
        Edge(
            id="e-merge-success",
            source="merge-gate",
            target="success",
            path=EdgePath.SUCCESS,
        ),
        Edge(
            id="e-merge-stop",
            source="merge-gate",
            target="stop",
            path=EdgePath.FAILURE,
        ),
    ]

    return Workflow(
        id=workflow_id, name=name, version="1.0.0", nodes=nodes, edges=edges
    )
