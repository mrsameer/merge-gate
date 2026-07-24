// T019 — React Flow canvas base rendering.
//
// spec.md FR-026/FR-026a require the canvas to present the default four-role
// loop (Input, Success Criteria, Human Gate, Planning, Execution, Validator,
// Decision, Success, Stop) as typed nodes showing name/type/status, with
// editing (add/connect/drag) reserved for the node-library task (T058). This
// pins down the read-only base render before any editing affordances exist.

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { GraphCanvas } from "../../src/canvas/GraphCanvas";
import {
  DEFAULT_WORKFLOW,
  DEFAULT_NODE_POSITIONS,
} from "../../src/canvas/defaultWorkflow";
import { toFlowEdges } from "../../src/canvas/toFlowGraph";

describe("GraphCanvas", () => {
  it("renders every node of the default four-role loop with its name, type, and status", () => {
    render(
      <GraphCanvas
        workflow={DEFAULT_WORKFLOW}
        positions={DEFAULT_NODE_POSITIONS}
      />,
    );

    expect(DEFAULT_WORKFLOW.nodes.length).toBe(9);

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
      "HumanGate",
      "Validator",
      "Decision",
      "Success",
      "Stop",
    ]) {
      expect(typesByNode.filter((t) => t === required)).toHaveLength(1);
    }
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

  it("renders read-only: no editing affordances for adding, connecting, or deleting nodes", () => {
    render(
      <GraphCanvas
        workflow={DEFAULT_WORKFLOW}
        positions={DEFAULT_NODE_POSITIONS}
      />,
    );

    expect(
      screen.queryByRole("button", { name: /add node/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /delete node/i }),
    ).not.toBeInTheDocument();
  });
});
