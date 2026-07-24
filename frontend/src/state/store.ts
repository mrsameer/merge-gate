// Shared UI state for the minimal run-control wiring (T030): which node is
// selected, the objective being entered, the active run with its draft
// contract, and the live per-node statuses / event log the console renders.
// The inspector/ and console/ panels read and mutate this store; the REST
// calls themselves stay in those panels via the api client (../api).

import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import type {
  Clarification,
  Contract,
  Criterion,
  Policy,
  Run,
  RunStatus,
} from "../api";
import {
  DEFAULT_NODE_POSITIONS,
  DEFAULT_WORKFLOW,
} from "../canvas/defaultWorkflow";
import {
  addWorkflowNode,
  connectWorkflowNodes,
  defaultPosition,
  layoutWorkflow,
  moveWorkflowNode,
  removeWorkflowNode,
  type NodePositions,
} from "../canvas/workflowEditing";
import type { EdgePath, NodeConfig, NodeType, Workflow } from "../canvas/types";

export const DEFAULT_POLICY: Policy = {
  protected_paths: ["app/auth/**", "tests/acceptance/**"],
  forbidden_diff_patterns: [
    "pytest.mark.skip",
    "eslint-disable",
    "assert True",
  ],
};

export interface ConsoleEvent {
  seq: number;
  type: string;
  data: Record<string, unknown>;
}

export interface RetryState {
  attempt: number;
  maxAttempts: number;
  reason: string;
  feedback?: Record<string, unknown>;
}

export interface AppState {
  workflow: Workflow;
  positions: NodePositions;
  selectedNodeId: string | null;
  objective: string;
  runId: string | null;
  contract: Contract | null;
  run: Run | null;
  nodeStatuses: Record<string, string>;
  events: ConsoleEvent[];
  lastEventId: number | null;
  retry: RetryState | null;
  clarification: Clarification | null;
  policy: Policy;

  setWorkflow: (workflow: Workflow, positions?: NodePositions) => void;
  renameWorkflow: (name: string) => void;
  addNode: (type: NodeType, position?: { x: number; y: number }) => void;
  removeNode: (nodeId: string) => void;
  moveNode: (nodeId: string, position: { x: number; y: number }) => void;
  connectNodes: (source: string, target: string, path: EdgePath) => void;
  updateNode: (
    nodeId: string,
    update: { name?: string; config?: Partial<NodeConfig> },
  ) => void;
  selectNode: (nodeId: string | null) => void;
  setObjective: (objective: string) => void;
  setRun: (run: Run) => void;
  setRunStatus: (status: RunStatus) => void;
  setContract: (contract: Contract | null) => void;
  setCriteria: (criteria: Criterion[]) => void;
  applyNodeStatus: (node: string, status: string) => void;
  appendEvent: (type: string, data: Record<string, unknown>) => void;
  setLastEventId: (eventId: number) => void;
  setRetry: (retry: RetryState | null) => void;
  setClarification: (clarification: Clarification | null) => void;
  setPolicy: (policy: Policy) => void;
  resetRun: () => void;
  reset: () => void;
}

function initialState() {
  return {
    workflow: structuredClone(DEFAULT_WORKFLOW),
    positions: structuredClone(DEFAULT_NODE_POSITIONS),
    selectedNodeId: null,
    objective: "",
    runId: null,
    contract: null,
    run: null,
    nodeStatuses: {},
    events: [],
    lastEventId: null,
    retry: null,
    clarification: null,
    policy: structuredClone(DEFAULT_POLICY),
  } satisfies Partial<AppState>;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      ...initialState(),

      setWorkflow: (workflow, positions) =>
        set({
          workflow,
          positions: positions ?? layoutWorkflow(workflow),
          selectedNodeId: null,
        }),

      renameWorkflow: (name) =>
        set((state) => ({ workflow: { ...state.workflow, name } })),

      addNode: (type, position) =>
        set((state) => {
          const result = addWorkflowNode(
            state.workflow,
            state.positions,
            type,
            position ?? defaultPosition(state.workflow.nodes.length),
          );
          return {
            workflow: result.workflow,
            positions: result.positions,
            selectedNodeId: result.node.id,
          };
        }),

      removeNode: (nodeId) =>
        set((state) => {
          const result = removeWorkflowNode(
            state.workflow,
            state.positions,
            nodeId,
          );
          return {
            workflow: result.workflow,
            positions: result.positions,
            selectedNodeId:
              state.selectedNodeId === nodeId ? null : state.selectedNodeId,
          };
        }),

      moveNode: (nodeId, position) =>
        set((state) => ({
          positions: moveWorkflowNode(state.positions, nodeId, position),
        })),

      connectNodes: (source, target, path) =>
        set((state) => ({
          workflow: connectWorkflowNodes(state.workflow, source, target, path),
        })),

      updateNode: (nodeId, update) =>
        set((state) => ({
          workflow: {
            ...state.workflow,
            nodes: state.workflow.nodes.map((node) =>
              node.id === nodeId
                ? {
                    ...node,
                    ...(update.name !== undefined ? { name: update.name } : {}),
                    ...(update.config
                      ? { config: { ...node.config, ...update.config } }
                      : {}),
                  }
                : node,
            ),
          },
        })),

      selectNode: (selectedNodeId) => set({ selectedNodeId }),

      setObjective: (objective) => set({ objective }),

      // A created/started run always carries its id, so keep runId in sync.
      setRun: (run) =>
        set((state) => ({
          run,
          runId: run.id,
          clarification: run.clarification ?? null,
          ...(state.runId !== null && state.runId !== run.id
            ? {
                nodeStatuses: {},
                events: [],
                lastEventId: null,
                retry: null,
              }
            : {}),
        })),

      setRunStatus: (status) =>
        set((state) => (state.run ? { run: { ...state.run, status } } : state)),

      setContract: (contract) => set({ contract }),

      setCriteria: (criteria) =>
        set((state) =>
          state.contract
            ? { contract: { ...state.contract, criteria } }
            : state,
        ),

      applyNodeStatus: (node, status) =>
        set((state) => ({
          nodeStatuses: { ...state.nodeStatuses, [node]: status },
        })),

      appendEvent: (type, data) =>
        set((state) => ({
          events: [
            ...state.events,
            { seq: state.events.length + 1, type, data },
          ],
        })),

      setLastEventId: (lastEventId) => set({ lastEventId }),

      setRetry: (retry) => set({ retry }),

      setClarification: (clarification) => set({ clarification }),
      setPolicy: (policy) => set({ policy }),

      // Clear run-scoped state for a fresh run while preserving the workflow
      // graph, node positions, and policy the operator has set up.
      resetRun: () =>
        set({
          objective: "",
          runId: null,
          contract: null,
          run: null,
          nodeStatuses: {},
          events: [],
          lastEventId: null,
          retry: null,
          clarification: null,
        }),

      reset: () => set(initialState()),
    }),
    {
      name: "mergegate-control-plane",
      storage: createJSONStorage(() => localStorage),
    },
  ),
);
