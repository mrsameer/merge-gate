import type {
  Workflow as ApiWorkflow,
  WorkflowEdgePayload,
  WorkflowNodePayload,
} from "../api";
import type { Workflow } from "./types";

export function toApiWorkflow(workflow: Workflow): ApiWorkflow {
  return {
    id: workflow.id,
    name: workflow.name,
    ...(workflow.version ? { version: workflow.version } : {}),
    nodes: workflow.nodes.map(({ id, type, name, config }) => ({
      id,
      type,
      name,
      ...(config ? { config } : {}),
    })),
    edges: workflow.edges.map(({ id, source, target, path }) => ({
      id,
      source,
      target,
      path,
    })),
  };
}

export function fromApiWorkflow(workflow: ApiWorkflow): Workflow {
  return {
    id: workflow.id,
    name: workflow.name,
    version: workflow.version,
    nodes: workflow.nodes.map((node: WorkflowNodePayload) => ({
      ...node,
      status: "idle",
    })),
    edges: workflow.edges.map((edge: WorkflowEdgePayload, index) => ({
      id: edge.id ?? `edge-${index}-${edge.source}-${edge.target}`,
      source: edge.source,
      target: edge.target,
      path: edge.path ?? "default",
    })),
  };
}
