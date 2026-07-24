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
const BRANCHING_NODE: NodeType[] = [
  "Agent",
  "Command",
  "Validator",
  "Decision",
  "HumanGate",
];

export function RoleNode({ id, data }: NodeProps<RoleNode>) {
  const { name, nodeType, status, summary, attemptNumber, latestResult } = data;

  return (
    <div
      className={`role-node role-node--${nodeType.toLowerCase()}`}
      data-testid={`canvas-node-${id}`}
      data-status={status}
    >
      {!NO_TARGET_HANDLE.includes(nodeType) && (
        <Handle id="default" type="target" position={Position.Left} />
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
        <>
          <Handle
            id="default"
            type="source"
            position={Position.Right}
            title="Default path"
          />
          {BRANCHING_NODE.includes(nodeType) && (
            <>
              <Handle
                id="success"
                type="source"
                position={Position.Right}
                style={{ top: "30%", background: "#16a34a" }}
                title="Success path"
              />
              <Handle
                id="failure"
                type="source"
                position={Position.Right}
                style={{ top: "70%", background: "#dc2626" }}
                title="Failure path"
              />
            </>
          )}
        </>
      )}
    </div>
  );
}
