import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { NodeLibraryPanel } from "../../src/layout/NodeLibraryPanel";

describe("NodeLibraryPanel", () => {
  it("offers every workflow node type for click-add and drag-to-canvas", () => {
    const onAddNode = vi.fn();
    render(<NodeLibraryPanel onAddNode={onAddNode} />);

    for (const type of [
      "Input",
      "Agent",
      "Command",
      "Validator",
      "Decision",
      "HumanGate",
      "Success",
      "Stop",
    ]) {
      const item = screen.getByTestId(`node-library-${type}`);
      expect(item).toHaveAttribute("draggable", "true");
      fireEvent.click(screen.getByRole("button", { name: `Add ${type}` }));
      expect(onAddNode).toHaveBeenLastCalledWith(type);
    }

    const setData = vi.fn();
    fireEvent.dragStart(screen.getByTestId("node-library-Agent"), {
      dataTransfer: { setData, effectAllowed: "none" },
    });
    expect(setData).toHaveBeenCalledWith(
      "application/x-mergegate-node",
      "Agent",
    );
  });
});
