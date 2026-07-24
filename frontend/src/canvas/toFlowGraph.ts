// Pure conversion from our Workflow model to React Flow's node/edge shape.
// Kept separate from GraphCanvas so it's testable without mounting React
// Flow itself (jsdom has no real layout, so edge-path rendering can't be
// asserted on directly in unit tests).

import { MarkerType, type Edge } from "@xyflow/react";
import { summarizeNodeConfig } from "./nodeSummary";
import type { RoleNode } from "./RoleNode";
import type { Workflow } from "./types";

// Matches .role-node in GraphCanvas.css, so React Flow can lay out edges
// immediately instead of waiting on a ResizeObserver measurement.
export const NODE_WIDTH = 160;
export const NODE_HEIGHT = 70;

const EDGE_PATH_COLOR: Record<string, string> = {
  default: "var(--edge-default, #94a3b8)",
  success: "var(--edge-success, #16a34a)",
  failure: "var(--edge-failure, #dc2626)",
};

export function toFlowNodes(
  workflow: Workflow,
  positions: Record<string, { x: number; y: number }>,
): RoleNode[] {
  return workflow.nodes.map((node) => ({
    id: node.id,
    type: "role",
    position: positions[node.id] ?? { x: 0, y: 0 },
    width: NODE_WIDTH,
    height: NODE_HEIGHT,
    data: {
      name: node.name,
      nodeType: node.type,
      status: node.status,
      summary: summarizeNodeConfig(node),
      attemptNumber: node.attemptNumber,
      latestResult: node.latestResult,
    },
    draggable: true,
    connectable: true,
    selectable: true,
  }));
}

export function toFlowEdges(workflow: Workflow): Edge[] {
  return workflow.edges.map((edge) => {
    const color = EDGE_PATH_COLOR[edge.path] ?? EDGE_PATH_COLOR.default;
    return {
      id: edge.id,
      source: edge.source,
      target: edge.target,
      sourceHandle: edge.path,
      type: "smoothstep",
      label: edge.path !== "default" ? edge.path : undefined,
      style: { stroke: color },
      markerEnd: { type: MarkerType.ArrowClosed, color },
    };
  });
}
