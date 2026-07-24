import { LoopCanvas } from "./canvas/LoopCanvas";
import { RunConsole } from "./console/RunConsole";
import { InspectorPanel } from "./inspector/InspectorPanel";

function App() {
  return (
    <main style={{ display: "grid", gap: "1rem", padding: "1rem" }}>
      <header>
        <h1>MergeGate</h1>
        <p>Loop engineering control plane — User Story 1</p>
      </header>
      <LoopCanvas />
      <InspectorPanel />
      <RunConsole />
    </main>
  );
}

export default App;
