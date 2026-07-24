// T019 — React Flow canvas base rendering.
//
// spec.md FR-026/FR-026a require the canvas to present the default four-role
// loop (Input, Success Criteria, Human Gate, Planning, Execution, Validator,
// Decision, Success, Stop) as typed nodes showing name/type/status, with
// editing (add/connect/drag) reserved for the node-library task (T058). This
// pins down the read-only base render before any editing affordances exist.

import { beforeEach, describe, it, expect, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { GraphCanvas } from "../../src/canvas/GraphCanvas";
import { CanvasArea } from "../../src/layout/CanvasArea";
import {
  DEFAULT_WORKFLOW,
  DEFAULT_NODE_POSITIONS,
} from "../../src/canvas/defaultWorkflow";
import { toFlowEdges, toFlowNodes } from "../../src/canvas/toFlowGraph";
import { useAppStore } from "../../src/state/store";

beforeEach(() => useAppStore.getState().reset());

describe("GraphCanvas", () => {
  it("renders every node of the default four-role loop with its name, type, and status", () => {
    render(
      <GraphCanvas
        workflow={DEFAULT_WORKFLOW}
        positions={DEFAULT_NODE_POSITIONS}
      />,
    );

    expect(DEFAULT_WORKFLOW.nodes.length).toBe(10);

    for (const node of DEFAULT_WORKFLOW.nodes) {
      const el = screen.getByTestId(`canvas-node-${node.id}`);
      expect(el).toHaveTextContent(node.name);
      expect(el).toHaveTextContent(node.type);
      expect(el).toHaveAttribute("data-status", node.status);
    }
  });

  it("includes exactly one node of each required type in the default loop", () => {
    render(
      <GraphCanvas
        workflow={DEFAULT_WORKFLOW}
        positions={DEFAULT_NODE_POSITIONS}
      />,
    );

    const typesByNode = DEFAULT_WORKFLOW.nodes.map((n) => n.type);
    for (const required of [
      "Input",
      "Validator",
      "Decision",
      "Success",
      "Stop",
    ]) {
      expect(typesByNode.filter((t) => t === required)).toHaveLength(1);
    }
    expect(typesByNode.filter((t) => t === "HumanGate")).toHaveLength(2);
    expect(typesByNode.filter((t) => t === "Agent")).toHaveLength(3);
  });

  it("passes every workflow edge through to React Flow, one-to-one", () => {
    // jsdom has no real layout, so React Flow won't compute rendered edge
    // paths in a unit test; the source/target/id mapping is verified here
    // directly, and the actual on-screen rendering is checked in-browser.
    const flowEdges = toFlowEdges(DEFAULT_WORKFLOW);

    expect(flowEdges).toHaveLength(DEFAULT_WORKFLOW.edges.length);
    for (const edge of DEFAULT_WORKFLOW.edges) {
      const flowEdge = flowEdges.find((e) => e.id === edge.id);
      expect(flowEdge).toBeDefined();
      expect(flowEdge?.source).toBe(edge.source);
      expect(flowEdge?.target).toBe(edge.target);
    }
  });

  it("renders the edges container so the default loop's connections are drawn", () => {
    const { container } = render(
      <GraphCanvas
        workflow={DEFAULT_WORKFLOW}
        positions={DEFAULT_NODE_POSITIONS}
      />,
    );

    expect(container.querySelector(".react-flow__edges")).toBeInTheDocument();
  });

  it("enables node dragging, selection, and connection authoring", () => {
    const nodes = toFlowNodes(DEFAULT_WORKFLOW, DEFAULT_NODE_POSITIONS);

    expect(nodes.every((node) => node.draggable)).toBe(true);
    expect(nodes.every((node) => node.connectable)).toBe(true);
    expect(nodes.every((node) => node.selectable)).toBe(true);
  });

  it("selects a clicked node so its settings can be inspected", () => {
    const onSelectNode = vi.fn();
    render(
      <GraphCanvas
        workflow={DEFAULT_WORKFLOW}
        positions={DEFAULT_NODE_POSITIONS}
        onSelectNode={onSelectNode}
      />,
    );

    fireEvent.click(screen.getByTestId("canvas-node-execution"));

    expect(onSelectNode).toHaveBeenCalledWith("execution");
  });

  it("accepts supported library drops and rejects unknown node types", () => {
    const onDropNode = vi.fn();
    const { getByTestId } = render(
      <GraphCanvas
        workflow={DEFAULT_WORKFLOW}
        positions={DEFAULT_NODE_POSITIONS}
        onDropNode={onDropNode}
      />,
    );
    const canvas = getByTestId("graph-canvas");

    fireEvent.drop(canvas, {
      clientX: 420,
      clientY: 260,
      dataTransfer: { getData: () => "Agent" },
    });
    expect(onDropNode).toHaveBeenCalledWith(
      "Agent",
      expect.objectContaining({ x: expect.any(Number), y: expect.any(Number) }),
    );

    fireEvent.drop(canvas, {
      clientX: 10,
      clientY: 10,
      dataTransfer: { getData: () => "Unknown" },
    });
    expect(onDropNode).toHaveBeenCalledTimes(1);
  });

  it("shows live attempt status and the deterministic validator result", () => {
    useAppStore.setState({
      run: {
        id: "run-1",
        workflow_id: "default-four-role-loop",
        objective: "objective",
        repo_ref: "demo-repo",
        status: "running",
        budgets: {
          max_attempts: 3,
          max_wall_clock_s: 600,
          max_model_calls: 20,
        },
        current_attempt: 2,
        cost: { tokens: 0, model_calls: 0, usd: 0 },
      },
      runId: "run-1",
      nodeStatuses: { execution: "running", validation: "failed" },
      events: [{ seq: 1, type: "verdict", data: { passed: false } }],
    });

    render(<CanvasArea />);

    expect(screen.getByTestId("canvas-node-execution")).toHaveTextContent(
      "Attempt 2",
    );
    const validator = screen.getByTestId("canvas-node-validator");
    expect(validator).toHaveAttribute("data-status", "failed");
    expect(validator).toHaveTextContent("Validation failed");
  });
});
