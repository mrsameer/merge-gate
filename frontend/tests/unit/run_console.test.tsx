// T030 — run console wiring test.
//
// The console renders the shared event log and per-node status list, and
// subscribes to the run's SSE stream when a run is active. The transport is
// injected (`connect`) so a fake can drive named events without an
// EventSource, mirroring tests/unit/sse_client.test.ts.

import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { RunConsole } from "../../src/console/RunConsole";
import type { RunEventHandlers } from "../../src/state/sseClient";
import { useAppStore } from "../../src/state/store";

beforeEach(() => {
  useAppStore.getState().reset();
});

describe("RunConsole", () => {
  it("renders logged events and node statuses from the store", () => {
    useAppStore.getState().appendEvent("verdict", { attempt: 1, passed: true });
    useAppStore.getState().applyNodeStatus("execution", "running");

    render(
      <RunConsole collapsed={false} onToggle={() => {}} connect={vi.fn()} />,
    );

    expect(screen.getByTestId("event-1")).toHaveTextContent("verdict");
    expect(screen.getByTestId("node-status-execution")).toHaveTextContent(
      "running",
    );
  });

  it("does not subscribe when there is no active run", () => {
    const connect = vi.fn();
    render(
      <RunConsole collapsed={false} onToggle={() => {}} connect={connect} />,
    );
    expect(connect).not.toHaveBeenCalled();
  });

  it("subscribes to the active run and reflects dispatched events", async () => {
    let captured: RunEventHandlers | undefined;
    const close = vi.fn();
    const connect = vi.fn((_runId: string, handlers: RunEventHandlers) => {
      captured = handlers;
      return { close };
    });

    useAppStore.setState({
      runId: "run-1",
      run: {
        id: "run-1",
        workflow_id: "wf-1",
        objective: "obj",
        repo_ref: "demo-repo",
        status: "running",
        budgets: {
          max_attempts: 3,
          max_wall_clock_s: 60,
          max_model_calls: 3,
        },
        current_attempt: 1,
        cost: { tokens: 0, model_calls: 0, usd: 0 },
      },
    });
    render(
      <RunConsole collapsed={false} onToggle={() => {}} connect={connect} />,
    );

    expect(connect).toHaveBeenCalledWith("run-1", expect.any(Object));

    act(() => captured?.node_status?.({ node: "execution", attempt: 1 }));
    expect(
      await screen.findByTestId("node-status-execution"),
    ).toHaveTextContent("running");

    act(() =>
      captured?.node_status?.({
        node: "policy",
        status: "blocked",
        attempt: 1,
      }),
    );
    expect(screen.getByTestId("node-status-policy")).toHaveTextContent(
      "blocked",
    );

    act(() => captured?.verdict?.({ attempt: 1, passed: false }));
    expect(screen.getByTestId("node-status-validation")).toHaveTextContent(
      "failed",
    );

    act(() => captured?.terminal?.({ status: "POLICY_BLOCKED" }));
    expect(screen.getByTestId("event-log")).toHaveTextContent("terminal");
    expect(useAppStore.getState().run?.status).toBe("POLICY_BLOCKED");
  });

  it("surfaces the current attempt and actionable retry reason", async () => {
    let captured: RunEventHandlers | undefined;
    useAppStore.setState({ runId: "run-1" });
    const connect = vi.fn((_runId: string, handlers: RunEventHandlers) => {
      captured = handlers;
      return { close: vi.fn() };
    });

    render(
      <RunConsole collapsed={false} onToggle={() => {}} connect={connect} />,
    );

    act(() =>
      captured?.retry?.({
        attempt: 2,
        max_attempts: 3,
        reason: "acceptance failed",
        feedback: {
          criterion: "task-tests",
          command: "pytest tests/test_orders.py -q",
          exit_code: 1,
        },
      }),
    );

    expect(await screen.findByTestId("attempt-progress")).toHaveTextContent(
      "Attempt 2 / 3",
    );
    expect(screen.getByTestId("retry-reason")).toHaveTextContent("task-tests");
    expect(screen.getByTestId("retry-reason")).toHaveTextContent(
      "pytest tests/test_orders.py -q",
    );
  });

  it("renders a truthful clarification panel and zero-attempt evidence", async () => {
    let captured: RunEventHandlers | undefined;
    useAppStore.setState({
      runId: "run-1",
      run: {
        id: "run-1",
        workflow_id: "default-four-role-loop",
        objective:
          "POST /orders must return both 200 and 201 for the same successful request.",
        repo_ref: "demo-repo",
        status: "running",
        budgets: {
          max_attempts: 3,
          max_wall_clock_s: 600,
          max_model_calls: 20,
        },
        current_attempt: 0,
        cost: { tokens: 0, model_calls: 0, usd: 0 },
      },
    });
    const connect = vi.fn((_runId: string, handlers: RunEventHandlers) => {
      captured = handlers;
      return { close: vi.fn() };
    });

    render(
      <RunConsole collapsed={false} onToggle={() => {}} connect={connect} />,
    );

    act(() =>
      captured?.terminal?.({
        status: "CLARIFICATION_REQUIRED",
        clarification: {
          reason:
            "The same successful request cannot require both HTTP 200 and HTTP 201.",
          conflicting_criteria: ["feature-exists"],
        },
        current_attempt: 0,
      }),
    );

    const panel = await screen.findByTestId("clarification-request");
    expect(panel).toHaveTextContent("Clarification required");
    expect(panel).toHaveTextContent("HTTP 200");
    expect(panel).toHaveTextContent("HTTP 201");
    expect(panel).toHaveTextContent("feature-exists");
    expect(panel).toHaveTextContent("No execution attempt was created");
    expect(screen.queryByText(/retrying because/i)).not.toBeInTheDocument();
  });

  it("closes the stream when the run console unmounts", () => {
    const close = vi.fn();
    const connect = vi.fn(() => ({ close }));
    useAppStore.setState({ runId: "run-1" });

    const { unmount } = render(
      <RunConsole collapsed={false} onToggle={() => {}} connect={connect} />,
    );
    unmount();

    expect(close).toHaveBeenCalledTimes(1);
  });

  it("hides the body when collapsed", () => {
    useAppStore.getState().appendEvent("gate", { attempt: 1 });
    render(
      <RunConsole collapsed={true} onToggle={() => {}} connect={vi.fn()} />,
    );
    expect(screen.queryByTestId("event-log")).not.toBeInTheDocument();
  });
});
