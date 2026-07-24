// T018 — app shell layout test.
//
// spec.md FR-026b requires the main screen to present five areas: a top bar,
// a node-library panel, the graph canvas, a node inspector, and a
// collapsible run console (FR-033). This test pins that structure down at
// the shell level, before the canvas/inspector/console own tasks (T019,
// T030, T058) fill in their real content.

import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { AppShell } from "../../src/layout/AppShell";

describe("AppShell", () => {
  it("renders all five control-plane areas", () => {
    render(<AppShell />);

    expect(screen.getByTestId("top-bar")).toBeInTheDocument();
    expect(screen.getByTestId("node-library-panel")).toBeInTheDocument();
    expect(screen.getByTestId("canvas-area")).toBeInTheDocument();
    expect(screen.getByTestId("inspector-panel")).toBeInTheDocument();
    expect(screen.getByTestId("run-console")).toBeInTheDocument();
  });

  it("starts with the run console expanded and collapses it on toggle", () => {
    render(<AppShell />);

    const toggle = screen.getByRole("button", { name: /run console/i });
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByTestId("run-console")).toHaveAttribute(
      "data-collapsed",
      "false",
    );

    fireEvent.click(toggle);

    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByTestId("run-console")).toHaveAttribute(
      "data-collapsed",
      "true",
    );
  });
});
