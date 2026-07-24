import { beforeEach, describe, expect, it } from "vitest";
import type { Run } from "../../src/api";
import { useAppStore } from "../../src/state/store";

const STORAGE_KEY = "mergegate-control-plane";

function runningRun(): Run {
  return {
    id: "run-refresh",
    workflow_id: "workflow",
    objective: "recover after refresh",
    repo_ref: "demo-repo",
    policy: { protected_paths: [], forbidden_diff_patterns: [] },
    status: "running",
    budgets: {
      max_attempts: 3,
      max_wall_clock_s: 60,
      max_model_calls: 10,
    },
    attempts: [],
    current_attempt: 1,
    cost: { tokens: 0, model_calls: 0, usd: 0 },
  };
}

describe("active run refresh recovery", () => {
  beforeEach(() => {
    localStorage.clear();
    useAppStore.getState().reset();
  });

  it("persists the active run and the last SSE event cursor", () => {
    useAppStore.getState().setRun(runningRun());
    const recoverable = useAppStore.getState() as unknown as {
      setLastEventId: (eventId: number) => void;
    };
    recoverable.setLastEventId(12);

    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}");
    expect(stored.state.runId).toBe("run-refresh");
    expect(stored.state.run.status).toBe("running");
    expect(stored.state.lastEventId).toBe(12);
  });
});
