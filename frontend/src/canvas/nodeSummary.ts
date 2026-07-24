// Short human-readable configuration summary shown on each canvas node
// (spec.md FR-026: "configuration summary").

import type { WorkflowNode } from "./types";

const TYPE_SUMMARY: Record<string, string> = {
  Input: "Objective entry",
  HumanGate: "Approval required",
  Decision: "Routes success / failure",
  Success: "Terminal: success",
  Stop: "Terminal: stop",
};

export function summarizeNodeConfig(node: WorkflowNode): string {
  const role = node.config?.role;
  if (role) {
    return `role: ${role}`;
  }
  return TYPE_SUMMARY[node.type] ?? "";
}
