// Shared UI state for the minimal run-control wiring (T030): which node is
// selected, the objective being entered, the active run with its draft
// contract, and the live per-node statuses / event log the console renders.
// The inspector/ and console/ panels read and mutate this store; the REST
// calls themselves stay in those panels via the api client (../api).

import { create } from "zustand";
import type {
  Clarification,
  Contract,
  Criterion,
  Policy,
  Run,
  RunStatus,
} from "../api";

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
  selectedNodeId: string | null;
  objective: string;
  runId: string | null;
  contract: Contract | null;
  run: Run | null;
  nodeStatuses: Record<string, string>;
  events: ConsoleEvent[];
  retry: RetryState | null;
  clarification: Clarification | null;
  policy: Policy;

  selectNode: (nodeId: string | null) => void;
  setObjective: (objective: string) => void;
  setRun: (run: Run) => void;
  setRunStatus: (status: RunStatus) => void;
  setContract: (contract: Contract | null) => void;
  setCriteria: (criteria: Criterion[]) => void;
  applyNodeStatus: (node: string, status: string) => void;
  appendEvent: (type: string, data: Record<string, unknown>) => void;
  setRetry: (retry: RetryState | null) => void;
  setClarification: (clarification: Clarification | null) => void;
  setPolicy: (policy: Policy) => void;
  reset: () => void;
}

const initialState = {
  selectedNodeId: null,
  objective: "",
  runId: null,
  contract: null,
  run: null,
  nodeStatuses: {},
  events: [],
  retry: null,
  clarification: null,
  policy: DEFAULT_POLICY,
} satisfies Partial<AppState>;

export const useAppStore = create<AppState>((set) => ({
  ...initialState,

  selectNode: (selectedNodeId) => set({ selectedNodeId }),

  setObjective: (objective) => set({ objective }),

  // A created/started run always carries its id, so keep runId in sync.
  setRun: (run) =>
    set({
      run,
      runId: run.id,
      clarification: run.clarification ?? null,
    }),

  setRunStatus: (status) =>
    set((state) => (state.run ? { run: { ...state.run, status } } : state)),

  setContract: (contract) => set({ contract }),

  setCriteria: (criteria) =>
    set((state) =>
      state.contract ? { contract: { ...state.contract, criteria } } : state,
    ),

  applyNodeStatus: (node, status) =>
    set((state) => ({
      nodeStatuses: { ...state.nodeStatuses, [node]: status },
    })),

  appendEvent: (type, data) =>
    set((state) => ({
      events: [...state.events, { seq: state.events.length + 1, type, data }],
    })),

  setRetry: (retry) => set({ retry }),

  setClarification: (clarification) => set({ clarification }),
  setPolicy: (policy) => set({ policy }),

  reset: () => set({ ...initialState }),
}));
