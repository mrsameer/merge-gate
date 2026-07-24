// React Flow canvas base rendering (T019): renders a Workflow's nodes and
// edges read-only. Authoring (add/connect/drag nodes) is T058's job; live
// status/inspector wiring is T030's.

import { useMemo } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { RoleNode } from "./RoleNode";
import { toFlowNodes, toFlowEdges } from "./toFlowGraph";
import type { Workflow } from "./types";
import "./GraphCanvas.css";

const nodeTypes = { role: RoleNode };

interface GraphCanvasProps {
  workflow: Workflow;
  positions: Record<string, { x: number; y: number }>;
  onSelectNode?: (nodeId: string) => void;
}

export function GraphCanvas({
  workflow,
  positions,
  onSelectNode,
}: GraphCanvasProps) {
  const nodes = useMemo(
    () => toFlowNodes(workflow, positions),
    [workflow, positions],
  );
  const edges = useMemo(() => toFlowEdges(workflow), [workflow]);

  return (
    <ReactFlowProvider>
      <div className="graph-canvas" data-testid="graph-canvas">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          onNodeClick={(_, node) => onSelectNode?.(node.id)}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          minZoom={0.1}
        >
          <Background />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
    </ReactFlowProvider>
  );
}
