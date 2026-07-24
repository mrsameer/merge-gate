// Five-area main-screen layout (spec.md FR-026b): top bar, node-library
// panel, graph canvas, node inspector, collapsible run console.

import { useState } from "react";
import { TopBar } from "./TopBar";
import { NodeLibraryPanel } from "./NodeLibraryPanel";
import { CanvasArea } from "./CanvasArea";
import { InspectorPanel } from "../inspector/InspectorPanel";
import { RunConsole } from "../console/RunConsole";
import { EvidencePanel } from "../evidence/EvidencePanel";
import { useAppStore } from "../state/store";
import "./AppShell.css";

export function AppShell() {
  const [consoleCollapsed, setConsoleCollapsed] = useState(false);
  const runId = useAppStore((state) => state.runId);
  const runStatus = useAppStore((state) => state.run?.status);
  const currentAttempt = useAppStore(
    (state) => state.run?.current_attempt ?? 0,
  );
  const hasCompletedVerdict = useAppStore((state) =>
    state.events.some((event) => event.type === "verdict"),
  );

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
      <EvidencePanel
        runId={runId}
        runStatus={runStatus}
        currentAttempt={currentAttempt}
        hasCompletedVerdict={hasCompletedVerdict}
      />
    </div>
  );
}
