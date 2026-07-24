// Five-area main-screen layout (spec.md FR-026b): top bar, node-library
// panel, graph canvas, node inspector, collapsible run console.

import { useState } from "react";
import { TopBar } from "./TopBar";
import { NodeLibraryPanel } from "./NodeLibraryPanel";
import { CanvasArea } from "./CanvasArea";
import { InspectorPanel } from "./InspectorPanel";
import { RunConsole } from "./RunConsole";
import "./AppShell.css";

export function AppShell() {
  const [consoleCollapsed, setConsoleCollapsed] = useState(false);

  return (
    <div className="app-shell">
      <TopBar />
      <div className="app-shell__body">
        <NodeLibraryPanel />
        <CanvasArea />
        <InspectorPanel />
      </div>
      <RunConsole
        collapsed={consoleCollapsed}
        onToggle={() => setConsoleCollapsed((collapsed) => !collapsed)}
      />
    </div>
  );
}
