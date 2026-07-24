import { create } from "zustand";

import type { Contract, Run } from "../api/client";
import {
  approveCriteria,
  approveFinalGate,
  createRun,
  generateCriteria,
  getRun,
  startRun,
} from "../api/client";

interface RunState {
  objective: string;
  run: Run | null;
  contract: Contract | null;
  log: string[];
  replayLog: string;
  setObjective: (objective: string) => void;
  setReplayLog: (message: string) => void;
  submitObjective: () => Promise<void>;
  generateAndApprove: () => Promise<void>;
  executeRun: () => Promise<void>;
  finalize: () => Promise<void>;
  refresh: () => Promise<void>;
}

export const useRunStore = create<RunState>((set, get) => ({
  objective: "",
  run: null,
  contract: null,
  log: [],
  replayLog: "",
  setObjective: (objective) => set({ objective }),
  setReplayLog: (replayLog) => set({ replayLog }),
  submitObjective: async () => {
    const objective = get().objective.trim();
    if (!objective) return;
    const run = await createRun(objective);
    set({ run, log: [`Run ${run.id} created`] });
  },
  generateAndApprove: async () => {
    const run = get().run;
    if (!run) return;
    const generated = await generateCriteria(run.id);
    const approved = await approveCriteria(run.id);
    set({
      contract: approved,
      log: [
        ...get().log,
        `Contract generated (${generated.criteria.length} criteria)`,
        `Contract approved (${approved.frozen_hash?.slice(0, 8)}…)`,
      ],
    });
  },
  executeRun: async () => {
    const run = get().run;
    if (!run) return;
    const updated = await startRun(run.id);
    set({
      run: updated,
      log: [
        ...get().log,
        `Attempt ${updated.current_attempt}: verdict ${updated.status}`,
      ],
    });
  },
  finalize: async () => {
    const run = get().run;
    if (!run) return;
    const updated = await approveFinalGate(run.id);
    set({
      run: updated,
      log: [...get().log, `Terminal state ${updated.status}`],
    });
  },
  refresh: async () => {
    const run = get().run;
    if (!run) return;
    set({ run: await getRun(run.id) });
  },
}));
