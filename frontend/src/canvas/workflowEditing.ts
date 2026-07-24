import type {
  EdgePath,
  NodeConfig,
  NodeType,
  Workflow,
  WorkflowNode,
} from "./types";

export type NodePositions = Record<string, { x: number; y: number }>;

const DEFAULT_CONFIG: Partial<Record<NodeType, NodeConfig>> = {
  Agent: {
    instructions: "",
    provider: "gemini",
    model: "gemini-2.5-flash",
    tools: [],
    retry_limit: 2,
    timeout_s: 300,
  },
  Command: { command: "", timeout_s: 300 },
  Validator: { criteria_ref: "", timeout_s: 300 },
  Decision: { completion_condition: "" },
  HumanGate: { completion_condition: "operator_approval" },
};

function generatedId(type: NodeType): string {
  const suffix =
    globalThis.crypto?.randomUUID?.() ??
    `${Date.now()}-${Math.floor(Math.random() * 10000)}`;
  return `${type.replace(/([a-z])([A-Z])/g, "$1-$2").toLowerCase()}-${suffix}`;
}

export function addWorkflowNode(
  workflow: Workflow,
  positions: NodePositions,
  type: NodeType,
  position: { x: number; y: number },
  id = generatedId(type),
): { workflow: Workflow; positions: NodePositions; node: WorkflowNode } {
  const node: WorkflowNode = {
    id,
    type,
    name: type === "HumanGate" ? "Human Gate" : type,
    ...(DEFAULT_CONFIG[type] ? { config: { ...DEFAULT_CONFIG[type] } } : {}),
    status: "idle",
  };
  return {
    workflow: { ...workflow, nodes: [...workflow.nodes, node] },
    positions: { ...positions, [id]: position },
    node,
  };
}

export function moveWorkflowNode(
  positions: NodePositions,
  nodeId: string,
  position: { x: number; y: number },
): NodePositions {
  return { ...positions, [nodeId]: position };
}

export function connectWorkflowNodes(
  workflow: Workflow,
  source: string,
  target: string,
  path: EdgePath,
): Workflow {
  if (source === target) return workflow;
  const sourceNode = workflow.nodes.find((node) => node.id === source);
  if (!sourceNode) return workflow;

  const configKey =
    path === "success"
      ? "success_path"
      : path === "failure"
        ? "failure_path"
        : null;
  const edgesWithoutPath = workflow.edges.filter(
    (edge) => !(edge.source === source && edge.path === path),
  );

  if (!target) {
    const nodes = configKey
      ? workflow.nodes.map((node) =>
          node.id === source
            ? { ...node, config: { ...node.config, [configKey]: "" } }
            : node,
        )
      : workflow.nodes;
    return { ...workflow, nodes, edges: edgesWithoutPath };
  }

  const targetNode = workflow.nodes.find((node) => node.id === target);
  if (!targetNode) return workflow;

  const edges = [
    ...edgesWithoutPath,
    {
      id: `edge-${source}-${path}-${target}`,
      source,
      target,
      path,
    },
  ];
  const nodes = configKey
    ? workflow.nodes.map((node) =>
        node.id === source
          ? {
              ...node,
              config: { ...node.config, [configKey]: target },
            }
          : node,
      )
    : workflow.nodes;
  return { ...workflow, nodes, edges };
}

export function defaultPosition(index: number): { x: number; y: number } {
  return {
    x: 80 + (index % 4) * 210,
    y: 80 + Math.floor(index / 4) * 150,
  };
}

export function layoutWorkflow(workflow: Workflow): NodePositions {
  return Object.fromEntries(
    workflow.nodes.map((node, index) => [node.id, defaultPosition(index)]),
  );
}
