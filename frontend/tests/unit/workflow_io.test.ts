import { describe, expect, it } from "vitest";
import { DEFAULT_WORKFLOW } from "../../src/canvas/defaultWorkflow";
import { fromApiWorkflow, toApiWorkflow } from "../../src/canvas/workflowIO";

describe("workflow API round trip", () => {
  it("strips runtime fields on export and restores idle runtime state on import", () => {
    const edited = {
      ...DEFAULT_WORKFLOW,
      nodes: DEFAULT_WORKFLOW.nodes.map((node) =>
        node.id === "execution"
          ? {
              ...node,
              status: "running" as const,
              attemptNumber: 2,
              latestResult: "working",
              config: {
                ...node.config,
                instructions: "Implement the plan",
                provider: "gemini",
                model: "gemini-2.5-flash",
                tools: ["shell"],
              },
            }
          : node,
      ),
    };

    const payload = toApiWorkflow(edited);
    expect(payload.nodes[4]).not.toHaveProperty("status");
    expect(payload.nodes[4]).not.toHaveProperty("attemptNumber");
    expect(payload.nodes[4]).toMatchObject({
      config: {
        instructions: "Implement the plan",
        provider: "gemini",
        model: "gemini-2.5-flash",
        tools: ["shell"],
      },
    });

    const reconstructed = fromApiWorkflow(payload);
    expect(reconstructed.nodes[4]).toMatchObject({
      status: "idle",
      config: edited.nodes[4].config,
    });
    expect(toApiWorkflow(reconstructed)).toEqual(payload);
  });
});
