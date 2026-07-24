import { describe, expect, it } from "vitest";
import {
  addWorkflowNode,
  connectWorkflowNodes,
  moveWorkflowNode,
} from "../../src/canvas/workflowEditing";
import { DEFAULT_WORKFLOW } from "../../src/canvas/defaultWorkflow";

describe("workflow authoring helpers", () => {
  it("adds a typed node at the dropped canvas position", () => {
    const result = addWorkflowNode(
      DEFAULT_WORKFLOW,
      {},
      "Command",
      { x: 320, y: 180 },
      "command-custom",
    );

    expect(result.workflow.nodes.at(-1)).toMatchObject({
      id: "command-custom",
      type: "Command",
      name: "Command",
      config: { command: "", timeout_s: 300 },
      status: "idle",
    });
    expect(result.positions["command-custom"]).toEqual({ x: 320, y: 180 });
  });

  it("moves nodes and connects labeled success/failure paths as graph data", () => {
    const moved = moveWorkflowNode({}, "decision", { x: 400, y: 250 });
    expect(moved.decision).toEqual({ x: 400, y: 250 });

    const withSuccess = connectWorkflowNodes(
      DEFAULT_WORKFLOW,
      "decision",
      "success",
      "success",
    );
    const withFailure = connectWorkflowNodes(
      withSuccess,
      "decision",
      "stop",
      "failure",
    );

    expect(withFailure.edges).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          source: "decision",
          target: "success",
          path: "success",
        }),
        expect.objectContaining({
          source: "decision",
          target: "stop",
          path: "failure",
        }),
      ]),
    );
    expect(
      withFailure.edges.filter(
        (edge) => edge.source === "decision" && edge.path === "failure",
      ),
    ).toHaveLength(1);
  });
});
