import { LoopCanvas } from "./canvas/LoopCanvas";
import { RunConsole } from "./console/RunConsole";
import { EvidencePanel } from "./evidence/EvidencePanel";
import { InspectorPanel } from "./inspector/InspectorPanel";

function App() {
  return (
    <main style={{ display: "grid", gap: "1rem", padding: "1rem" }}>
      <header>
        <h1>MergeGate</h1>
        <p>Loop engineering control plane — User Stories 1 &amp; 2</p>
      </header>
      <LoopCanvas />
      <InspectorPanel />
      <RunConsole />
      <EvidencePanel />
    </main>
  );
}

export default App;
