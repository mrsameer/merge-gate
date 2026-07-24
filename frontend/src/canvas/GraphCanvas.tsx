// React Flow canvas base rendering (T019): renders a Workflow's nodes and
// edges read-only. Authoring (add/connect/drag nodes) is T058's job; live
// status/inspector wiring is T030's.

import { useMemo, type DragEvent } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  useReactFlow,
  type Connection,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { RoleNode } from "./RoleNode";
import { toFlowNodes, toFlowEdges } from "./toFlowGraph";
import type { Workflow } from "./types";
import type { EdgePath, NodeType } from "./types";
import { NODE_DRAG_MIME, WORKFLOW_NODE_TYPES } from "./nodeLibrary";
import "./GraphCanvas.css";

const nodeTypes = { role: RoleNode };

interface GraphCanvasProps {
  workflow: Workflow;
  positions: Record<string, { x: number; y: number }>;
  onSelectNode?: (nodeId: string) => void;
  onMoveNode?: (nodeId: string, position: { x: number; y: number }) => void;
  onConnectNodes?: (source: string, target: string, path: EdgePath) => void;
  onDropNode?: (type: NodeType, position: { x: number; y: number }) => void;
}

export function GraphCanvas({
  workflow,
  positions,
  onSelectNode,
  onMoveNode,
  onConnectNodes,
  onDropNode,
}: GraphCanvasProps) {
  return (
    <ReactFlowProvider>
      <GraphCanvasInner
        workflow={workflow}
        positions={positions}
        onSelectNode={onSelectNode}
        onMoveNode={onMoveNode}
        onConnectNodes={onConnectNodes}
        onDropNode={onDropNode}
      />
    </ReactFlowProvider>
  );
}

function GraphCanvasInner({
  workflow,
  positions,
  onSelectNode,
  onMoveNode,
  onConnectNodes,
  onDropNode,
}: GraphCanvasProps) {
  const nodes = useMemo(
    () => toFlowNodes(workflow, positions),
    [workflow, positions],
  );
  const edges = useMemo(() => toFlowEdges(workflow), [workflow]);
  const { screenToFlowPosition } = useReactFlow();

  const connect = (connection: Connection) => {
    if (!connection.source || !connection.target) return;
    const path: EdgePath =
      connection.sourceHandle === "success" ||
      connection.sourceHandle === "failure"
        ? connection.sourceHandle
        : "default";
    onConnectNodes?.(connection.source, connection.target, path);
  };

  const drop = (event: DragEvent) => {
    event.preventDefault();
    const type = event.dataTransfer.getData(NODE_DRAG_MIME) as NodeType;
    if (!WORKFLOW_NODE_TYPES.includes(type)) return;
    onDropNode?.(
      type,
      screenToFlowPosition({ x: event.clientX, y: event.clientY }),
    );
  };

  return (
    <div
      className="graph-canvas"
      data-testid="graph-canvas"
      onDragOver={(event) => {
        event.preventDefault();
        event.dataTransfer.dropEffect = "copy";
      }}
      onDrop={drop}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        nodesDraggable
        nodesConnectable
        elementsSelectable
        onNodeClick={(_, node) => onSelectNode?.(node.id)}
        onNodeDragStop={(_, node) =>
          onMoveNode?.(node.id, { x: node.position.x, y: node.position.y })
        }
        onConnect={connect}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.1}
      >
        <Background />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
