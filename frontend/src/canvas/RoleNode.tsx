// Custom React Flow node rendering one typed workflow node: name, type,
// status, and configuration summary (spec.md FR-026), plus attempt number
// and latest result once a run populates them (T030).

import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";
import type { NodeStatus, NodeType } from "./types";

export type RoleNodeData = {
  name: string;
  nodeType: NodeType;
  status: NodeStatus;
  summary: string;
  attemptNumber?: number;
  latestResult?: string;
};

export type RoleNode = Node<RoleNodeData, "role">;

const NO_TARGET_HANDLE: NodeType[] = ["Input"];
const NO_SOURCE_HANDLE: NodeType[] = ["Success", "Stop"];

export function RoleNode({ id, data }: NodeProps<RoleNode>) {
  const { name, nodeType, status, summary, attemptNumber, latestResult } = data;

  return (
    <div
      className={`role-node role-node--${nodeType.toLowerCase()}`}
      data-testid={`canvas-node-${id}`}
      data-status={status}
    >
      {!NO_TARGET_HANDLE.includes(nodeType) && (
        <Handle type="target" position={Position.Left} />
      )}
      <div className="role-node__header">
        <span className="role-node__name">{name}</span>
        <span className="role-node__type">{nodeType}</span>
      </div>
      <div className="role-node__status">{status}</div>
      {summary && <div className="role-node__summary">{summary}</div>}
      {attemptNumber !== undefined && (
        <div className="role-node__attempt">Attempt {attemptNumber}</div>
      )}
      {latestResult && <div className="role-node__result">{latestResult}</div>}
      {!NO_SOURCE_HANDLE.includes(nodeType) && (
        <Handle type="source" position={Position.Right} />
      )}
    </div>
  );
}
