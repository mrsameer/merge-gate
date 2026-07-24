import type { NodeType } from "./types";

export const WORKFLOW_NODE_TYPES = [
  "Input",
  "Agent",
  "Command",
  "Validator",
  "Decision",
  "HumanGate",
  "Success",
  "Stop",
] as const satisfies readonly NodeType[];

export const NODE_DRAG_MIME = "application/x-mergegate-node";
