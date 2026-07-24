// The default four-role loop (spec.md summary; quickstart.md Scenario A step 2):
// Input -> Success Criteria -> Human Gate -> Planning -> Execution -> Validator
// -> Decision -> Success/Stop, with failed attempts returning to Planning while
// attempts remain (spec.md FR-012) and otherwise stopping safely.

import type { Workflow } from "./types";

export const DEFAULT_WORKFLOW: Workflow = {
  id: "default-four-role-loop",
  name: "Default Four-Role Loop",
  version: "1.0.0",
  nodes: [
    { id: "input", type: "Input", name: "Input", status: "idle" },
    {
      id: "success-criteria",
      type: "Agent",
      name: "Success Criteria",
      config: { role: "success_criteria" },
      status: "idle",
    },
    {
      id: "contract-gate",
      type: "HumanGate",
      name: "Contract Gate",
      status: "idle",
    },
    {
      id: "planning",
      type: "Agent",
      name: "Planning",
      config: { role: "planning" },
      status: "idle",
    },
    {
      id: "execution",
      type: "Agent",
      name: "Execution",
      config: { role: "execution" },
      status: "idle",
    },
    {
      id: "validator",
      type: "Validator",
      name: "Validator",
      config: { role: "validation" },
      status: "idle",
    },
    { id: "decision", type: "Decision", name: "Decision", status: "idle" },
    {
      id: "merge-gate",
      type: "HumanGate",
      name: "Merge Gate",
      status: "idle",
    },
    { id: "success", type: "Success", name: "Success", status: "idle" },
    { id: "stop", type: "Stop", name: "Stop", status: "idle" },
  ],
  edges: [
    {
      id: "e-input-criteria",
      source: "input",
      target: "success-criteria",
      path: "default",
    },
    {
      id: "e-criteria-gate",
      source: "success-criteria",
      target: "contract-gate",
      path: "default",
    },
    {
      id: "e-gate-planning",
      source: "contract-gate",
      target: "planning",
      path: "success",
    },
    {
      id: "e-planning-execution",
      source: "planning",
      target: "execution",
      path: "default",
    },
    {
      id: "e-execution-validator",
      source: "execution",
      target: "validator",
      path: "default",
    },
    {
      id: "e-validator-decision",
      source: "validator",
      target: "decision",
      path: "default",
    },
    {
      id: "e-decision-merge",
      source: "decision",
      target: "merge-gate",
      path: "success",
    },
    {
      id: "e-decision-retry",
      source: "decision",
      target: "planning",
      path: "failure",
    },
    {
      id: "e-merge-success",
      source: "merge-gate",
      target: "success",
      path: "success",
    },
    {
      id: "e-merge-stop",
      source: "merge-gate",
      target: "stop",
      path: "failure",
    },
  ],
};

export const DEFAULT_NODE_POSITIONS: Record<string, { x: number; y: number }> =
  {
    input: { x: 0, y: 160 },
    "success-criteria": { x: 220, y: 160 },
    "contract-gate": { x: 440, y: 160 },
    planning: { x: 660, y: 160 },
    execution: { x: 880, y: 160 },
    validator: { x: 1100, y: 160 },
    decision: { x: 1320, y: 160 },
    "merge-gate": { x: 1540, y: 160 },
    success: { x: 1760, y: 40 },
    stop: { x: 1760, y: 280 },
  };
