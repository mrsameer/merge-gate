import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ApiClient, Contract, Run } from "../../src/api";
import { TopBar } from "../../src/layout/TopBar";
import { useAppStore } from "../../src/state/store";

function run(status: Run["status"], currentAttempt = 2): Run {
  return {
    id: "run-1",
    workflow_id: "default-four-role-loop",
    objective: "objective",
    repo_ref: "demo-repo",
    status,
    budgets: { max_attempts: 3, max_wall_clock_s: 600, max_model_calls: 20 },
    current_attempt: currentAttempt,
    cost: { tokens: 0, model_calls: 0, usd: 0 },
  };
}

beforeEach(() => useAppStore.getState().reset());

describe("TopBar", () => {
  it("shows live state and wires save, start, pause, resume, stop, and export", async () => {
    const updateWorkflow = vi
      .fn()
      .mockImplementation((_id, workflow) => Promise.resolve(workflow));
    const startRun = vi.fn().mockResolvedValue(run("running"));
    const pauseRun = vi.fn().mockResolvedValue(run("paused"));
    const resumeRun = vi.fn().mockResolvedValue(run("running"));
    const stopRun = vi.fn().mockResolvedValue(run("CANCELLED"));
    const exportWorkflow = vi.fn().mockResolvedValue("name: workflow\n");
    const onDownload = vi.fn();
    const client = {
      updateWorkflow,
      startRun,
      pauseRun,
      resumeRun,
      stopRun,
      exportWorkflow,
    } as unknown as ApiClient;
    const approved = {
      id: "contract-1",
      run_id: "run-1",
      mode: "hybrid",
      criteria: [],
      approved: true,
      frozen_hash: "hash",
    } satisfies Contract;
    useAppStore.setState({
      run: run("awaiting_gate", 0),
      runId: "run-1",
      contract: approved,
    });

    render(<TopBar client={client} onDownload={onDownload} />);

    expect(screen.getByTestId("attempt-counter")).toHaveTextContent(
      "Attempt 0 / 3",
    );
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(updateWorkflow).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole("button", { name: "Run" }));
    await waitFor(() => expect(startRun).toHaveBeenCalledWith("run-1"));
    expect(screen.getByTestId("run-status")).toHaveTextContent("running");
    expect(screen.getByTestId("attempt-counter")).toHaveTextContent(
      "Attempt 2 / 3",
    );

    fireEvent.click(screen.getByRole("button", { name: "Pause" }));
    await waitFor(() => expect(pauseRun).toHaveBeenCalledWith("run-1"));
    expect(screen.getByTestId("run-status")).toHaveTextContent("paused");

    fireEvent.click(screen.getByRole("button", { name: "Resume" }));
    await waitFor(() => expect(resumeRun).toHaveBeenCalledWith("run-1"));

    fireEvent.click(screen.getByRole("button", { name: "Stop" }));
    await waitFor(() => expect(stopRun).toHaveBeenCalledWith("run-1"));
    expect(screen.getByTestId("run-status")).toHaveTextContent("CANCELLED");

    fireEvent.change(screen.getByLabelText("Export format"), {
      target: { value: "yaml" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Export" }));
    await waitFor(() =>
      expect(exportWorkflow).toHaveBeenCalledWith(
        "default-four-role-loop",
        "yaml",
      ),
    );
    expect(onDownload).toHaveBeenCalledWith(
      "default-four-role-loop.yaml",
      "name: workflow\n",
      "application/yaml",
    );
  });
});
