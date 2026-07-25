// T030 — inspector panel wiring test.
//
// When the Input node is selected the inspector drives the
// contract-before-code lifecycle: objective entry updates shared state,
// creating a run stores its id, and generate/edit/approve/start each call the
// REST client with the right arguments. The client is mocked so no backend is
// needed; state is asserted against the zustand store.

import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { InspectorPanel } from "../../src/inspector/InspectorPanel";
import type { ApiClient, Contract, Run } from "../../src/api";
import { useAppStore } from "../../src/state/store";

function makeRun(overrides: Partial<Run> = {}): Run {
  return {
    id: "run-1",
    workflow_id: "default-four-role-loop",
    objective: "obj",
    repo_ref: "demo-repo",
    status: "awaiting_gate",
    budgets: { max_attempts: 3, max_wall_clock_s: 600, max_model_calls: 20 },
    current_attempt: 0,
    cost: { tokens: 0, model_calls: 0, usd: 0 },
    ...overrides,
  };
}

function makeContract(overrides: Partial<Contract> = {}): Contract {
  return {
    id: "contract-run-1",
    run_id: "run-1",
    mode: "hybrid",
    approved: false,
    frozen_hash: "",
    criteria: [{ id: "c1", type: "command", priority: 1, command: "echo hi" }],
    ...overrides,
  };
}

beforeEach(() => {
  useAppStore.getState().reset();
});

describe("InspectorPanel", () => {
  it("prompts to select a node when nothing is selected", () => {
    render(<InspectorPanel client={{} as ApiClient} />);
    expect(screen.getByText(/select a node/i)).toBeInTheDocument();
  });

  it("updates the objective in the store as the user types", () => {
    useAppStore.getState().selectNode("input");
    render(<InspectorPanel client={{} as ApiClient} />);

    fireEvent.change(screen.getByLabelText("Objective"), {
      target: { value: "Add idempotency keys" },
    });

    expect(useAppStore.getState().objective).toBe("Add idempotency keys");
  });

  it("shows and edits only the selected Agent node's relevant settings", () => {
    useAppStore.getState().selectNode("execution");
    render(<InspectorPanel client={{} as ApiClient} />);

    expect(screen.getByLabelText("Node name")).toHaveValue("Execution");
    expect(screen.getByLabelText("Instructions")).toBeInTheDocument();
    expect(screen.getByLabelText("Node provider")).toBeInTheDocument();
    expect(screen.getByLabelText("Node model")).toBeInTheDocument();
    expect(screen.getByLabelText("Tools")).toBeInTheDocument();
    expect(screen.getByLabelText("Retry limit")).toBeInTheDocument();
    expect(screen.getByLabelText("Timeout")).toBeInTheDocument();
    expect(screen.getByLabelText("Success path")).toBeInTheDocument();
    expect(screen.getByLabelText("Failure path")).toBeInTheDocument();
    expect(screen.queryByLabelText("Command")).not.toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Aider" })).toBeInTheDocument();
    expect(
      screen.getByRole("option", { name: "Claude Agent SDK" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Codex" })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Instructions"), {
      target: { value: "Implement the approved plan." },
    });

    expect(
      useAppStore
        .getState()
        .workflow.nodes.find((node) => node.id === "execution")?.config
        ?.instructions,
    ).toBe("Implement the approved plan.");
  });

  it("removes a configured path from both node config and graph edges", () => {
    useAppStore.getState().selectNode("decision");
    render(<InspectorPanel client={{} as ApiClient} />);

    fireEvent.change(screen.getByLabelText("Success path"), {
      target: { value: "merge-gate" },
    });
    expect(
      useAppStore
        .getState()
        .workflow.edges.some(
          (edge) => edge.source === "decision" && edge.path === "success",
        ),
    ).toBe(true);

    fireEvent.change(screen.getByLabelText("Success path"), {
      target: { value: "" },
    });

    const workflow = useAppStore.getState().workflow;
    expect(
      workflow.edges.some(
        (edge) => edge.source === "decision" && edge.path === "success",
      ),
    ).toBe(false);
    expect(
      workflow.nodes.find((node) => node.id === "decision")?.config
        ?.success_path,
    ).toBe("");
  });

  it("creates a run from the objective and stores the run id", async () => {
    const createRun = vi.fn().mockResolvedValue(makeRun());
    const client = { createRun } as unknown as ApiClient;
    useAppStore.getState().selectNode("input");
    useAppStore.getState().setObjective("Add idempotency keys");
    render(<InspectorPanel client={client} />);

    fireEvent.click(screen.getByRole("button", { name: /create run/i }));

    await waitFor(() => expect(useAppStore.getState().runId).toBe("run-1"));
    expect(createRun).toHaveBeenCalledWith(
      expect.objectContaining({
        workflow_id: "default-four-role-loop",
        objective: "Add idempotency keys",
        repo_ref: "demo-repo",
      }),
    );
  });

  it("shows the persisted run configuration after a page-level recovery", () => {
    useAppStore.getState().selectNode("input");
    useAppStore.getState().setRun(
      makeRun({
        repo_ref: "/worktrees/recovered-repo",
        provider: "gemini",
        model: "gemini-2.5-flash",
      }),
    );

    render(<InspectorPanel client={{} as ApiClient} />);

    expect(screen.getByLabelText("Repository")).toHaveValue(
      "/worktrees/recovered-repo",
    );
    expect(screen.getByLabelText("Provider")).toHaveValue("gemini");
    expect(screen.getByLabelText("Model")).toHaveValue("gemini-2.5-flash");
  });

  it("lets the operator choose Gemini and sends it with the run request", async () => {
    const createRun = vi
      .fn()
      .mockResolvedValue(makeRun({ provider: "gemini" }));
    const client = { createRun } as unknown as ApiClient;
    useAppStore.getState().selectNode("input");
    useAppStore.getState().setObjective("Add idempotency keys");
    render(<InspectorPanel client={client} />);

    fireEvent.change(screen.getByLabelText("Provider"), {
      target: { value: "gemini" },
    });
    fireEvent.change(screen.getByLabelText("Model"), {
      target: { value: "gemini-2.5-pro" },
    });
    fireEvent.change(screen.getByLabelText("Vertex location"), {
      target: { value: "asia-south1" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create run/i }));

    await waitFor(() =>
      expect(createRun).toHaveBeenCalledWith(
        expect.objectContaining({
          provider: "gemini",
          model: "gemini-2.5-pro",
          location: "asia-south1",
        }),
      ),
    );
  });

  it("surfaces editable policy config on the Validator and freezes it into a run", async () => {
    useAppStore.getState().selectNode("validator");
    const { rerender } = render(<InspectorPanel client={{} as ApiClient} />);

    const protectedPaths = screen.getByLabelText("Protected paths");
    const forbiddenPatterns = screen.getByLabelText("Forbidden diff patterns");
    expect(protectedPaths).toHaveValue("app/auth/**\ntests/acceptance/**");
    expect(forbiddenPatterns).toHaveValue(
      "pytest.mark.skip\neslint-disable\nassert True",
    );

    fireEvent.change(protectedPaths, {
      target: { value: "app/auth/**\ninfra/secrets/**" },
    });
    fireEvent.change(forbiddenPatterns, {
      target: { value: "pytest.mark.skip\nnoqa" },
    });

    const createRun = vi.fn().mockResolvedValue(makeRun());
    useAppStore.getState().selectNode("input");
    useAppStore.getState().setObjective("Add idempotency keys");
    rerender(<InspectorPanel client={{ createRun } as unknown as ApiClient} />);
    fireEvent.click(screen.getByRole("button", { name: /create run/i }));

    await waitFor(() =>
      expect(createRun).toHaveBeenCalledWith(
        expect.objectContaining({
          policy: {
            protected_paths: ["app/auth/**", "infra/secrets/**"],
            forbidden_diff_patterns: ["pytest.mark.skip", "noqa"],
          },
        }),
      ),
    );
  });

  it("generates, edits, approves criteria and starts the run", async () => {
    const generateCriteria = vi.fn().mockResolvedValue(makeContract());
    const updateCriteria = vi.fn().mockResolvedValue(
      makeContract({
        criteria: [
          { id: "c1", type: "command", priority: 1, command: "echo edited" },
        ],
      }),
    );
    const approveCriteria = vi
      .fn()
      .mockResolvedValue(makeContract({ approved: true }));
    const startRun = vi.fn().mockResolvedValue(makeRun({ status: "running" }));
    const client = {
      generateCriteria,
      updateCriteria,
      approveCriteria,
      startRun,
    } as unknown as ApiClient;

    useAppStore.setState({
      selectedNodeId: "input",
      runId: "run-1",
      run: makeRun(),
      objective: "obj",
    });
    render(<InspectorPanel client={client} />);

    // Generate criteria -> criterion command becomes editable.
    fireEvent.click(screen.getByRole("button", { name: /generate criteria/i }));
    const commandInput = await screen.findByLabelText("Command for c1");
    expect(commandInput).toHaveValue("echo hi");
    expect(generateCriteria).toHaveBeenCalledWith("run-1", "hybrid");

    // Edit the command, then save -> PUT /criteria with the edited list.
    fireEvent.change(commandInput, { target: { value: "echo edited" } });
    fireEvent.click(screen.getByRole("button", { name: /save criteria/i }));
    await waitFor(() =>
      expect(updateCriteria).toHaveBeenCalledWith("run-1", [
        expect.objectContaining({ id: "c1", command: "echo edited" }),
      ]),
    );

    // Approve -> contract frozen; Start button becomes enabled.
    fireEvent.click(screen.getByRole("button", { name: /approve criteria/i }));
    await waitFor(() =>
      expect(useAppStore.getState().contract?.approved).toBe(true),
    );
    expect(approveCriteria).toHaveBeenCalledWith("run-1");

    // Start the run.
    fireEvent.click(screen.getByRole("button", { name: /start run/i }));
    await waitFor(() => expect(startRun).toHaveBeenCalledWith("run-1"));
    await waitFor(() =>
      expect(useAppStore.getState().run?.status).toBe("running"),
    );
  });

  it("preserves a structured clarification returned when starting", async () => {
    const startRun = vi.fn().mockResolvedValue(
      makeRun({
        status: "CLARIFICATION_REQUIRED",
        clarification: {
          reason: "The same request cannot return both HTTP 200 and HTTP 201.",
          conflicting_criteria: ["feature-exists"],
        },
      }),
    );
    const client = { startRun } as unknown as ApiClient;
    useAppStore.setState({
      selectedNodeId: "input",
      runId: "run-1",
      run: makeRun(),
      objective: "obj",
      contract: makeContract({ approved: true }),
    });
    render(<InspectorPanel client={client} />);

    fireEvent.click(screen.getByRole("button", { name: /start run/i }));

    await waitFor(() =>
      expect(useAppStore.getState().run?.status).toBe("CLARIFICATION_REQUIRED"),
    );
    expect(useAppStore.getState().clarification).toEqual({
      reason: "The same request cannot return both HTTP 200 and HTTP 201.",
      conflicting_criteria: ["feature-exists"],
    });
    expect(screen.getByRole("button", { name: /start run/i })).toBeDisabled();
  });

  it("reports a generated clarification without presenting criteria to approve", async () => {
    const generateCriteria = vi.fn().mockResolvedValue({
      clarification: {
        reason: "The success statuses conflict.",
        conflicting_criteria: ["status-200", "status-201"],
      },
    });
    useAppStore.setState({
      selectedNodeId: "input",
      runId: "run-1",
      run: makeRun(),
      objective: "return both statuses",
    });
    render(
      <InspectorPanel client={{ generateCriteria } as unknown as ApiClient} />,
    );

    fireEvent.click(screen.getByRole("button", { name: /generate criteria/i }));

    expect(
      await screen.findByText(
        /clarification needed: the success statuses conflict/i,
      ),
    ).toBeInTheDocument();
    expect(useAppStore.getState().clarification).toEqual({
      reason: "The success statuses conflict.",
      conflicting_criteria: ["status-200", "status-201"],
    });
    expect(screen.queryByTestId("criteria-list")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /start run/i })).toBeDisabled();
  });

  it("refreshes the completed run and approves its final merge gate", async () => {
    const getRun = vi
      .fn()
      .mockResolvedValue(
        makeRun({ status: "awaiting_gate", current_attempt: 1 }),
      );
    const decideGate = vi
      .fn()
      .mockResolvedValue(makeRun({ status: "SUCCESS", current_attempt: 1 }));
    const client = { getRun, decideGate } as unknown as ApiClient;
    useAppStore.setState({
      selectedNodeId: "input",
      runId: "run-1",
      run: makeRun({ status: "running", current_attempt: 1 }),
      contract: makeContract({ approved: true }),
    });
    render(<InspectorPanel client={client} />);

    fireEvent.click(
      screen.getByRole("button", { name: /refresh run status/i }),
    );
    await waitFor(() =>
      expect(useAppStore.getState().run?.status).toBe("awaiting_gate"),
    );
    fireEvent.click(screen.getByRole("button", { name: /approve merge/i }));

    await waitFor(() =>
      expect(decideGate).toHaveBeenCalledWith("run-1", "final", "approve"),
    );
    expect(useAppStore.getState().run?.status).toBe("SUCCESS");
  });

  it("cancels and discards an unmerged run before starting over", async () => {
    const stopRun = vi.fn().mockResolvedValue(makeRun({ status: "CANCELLED" }));
    useAppStore.setState({
      selectedNodeId: "input",
      runId: "run-1",
      run: makeRun({ status: "awaiting_gate", current_attempt: 1 }),
      contract: makeContract({ approved: true }),
    });
    render(<InspectorPanel client={{ stopRun } as unknown as ApiClient} />);

    fireEvent.click(screen.getByRole("button", { name: /new run/i }));

    await waitFor(() => expect(stopRun).toHaveBeenCalledWith("run-1"));
    expect(useAppStore.getState().runId).toBeNull();
    expect(useAppStore.getState().run).toBeNull();
  });

  it("surfaces an api error message", async () => {
    const createRun = vi.fn().mockRejectedValue(new Error("boom"));
    const client = { createRun } as unknown as ApiClient;
    useAppStore.getState().selectNode("input");
    useAppStore.getState().setObjective("obj");
    render(<InspectorPanel client={client} />);

    fireEvent.click(screen.getByRole("button", { name: /create run/i }));

    expect(await screen.findByTestId("inspector-error")).toHaveTextContent(
      "boom",
    );
  });
});
