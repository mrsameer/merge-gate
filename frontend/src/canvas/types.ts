// Canvas node-graph types, mirroring specs/001-mergegate-control-plane/data-model.md
// (Workflow/Node/Edge) and contracts/workflow.schema.json. Owned by this task
// (T019); the REST client (T018, ../api/types.ts) intentionally leaves these
// as unknown[] and defers to here.

export type NodeType =
  | "Input"
  | "Agent"
  | "Command"
  | "Validator"
  | "Decision"
  | "HumanGate"
  | "Success"
  | "Stop";

export type NodeStatus =
  "idle" | "running" | "passed" | "failed" | "blocked" | "waiting" | "skipped";

export type AgentRole =
  "success_criteria" | "planning" | "execution" | "validation";

export type EdgePath = "default" | "success" | "failure";

export interface NodeConfig {
  role?: AgentRole;
  instructions?: string;
  provider?: string;
  model?: string;
  tools?: string[];
  command?: string;
  timeout_s?: number;
  criteria_ref?: string;
  retry_limit?: number;
  completion_condition?: string;
  success_path?: string;
  failure_path?: string;
}

export interface WorkflowNode {
  id: string;
  type: NodeType;
  name: string;
  config?: NodeConfig;
  status: NodeStatus;
  attemptNumber?: number;
  latestResult?: string;
}

export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  path: EdgePath;
}

export interface Workflow {
  id: string;
  name: string;
  version?: string;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
}
