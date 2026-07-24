// Node-library panel: the eight draggable node kinds (spec.md FR-026).
// Drag/drop-to-canvas wiring lands in T058.

const NODE_TYPES = [
  "Input",
  "Agent",
  "Command",
  "Validator",
  "Decision",
  "HumanGate",
  "Success",
  "Stop",
] as const;

export function NodeLibraryPanel() {
  return (
    <aside
      className="node-library-panel"
      data-testid="node-library-panel"
      aria-label="Node library"
    >
      <h2>Node library</h2>
      <ul>
        {NODE_TYPES.map((type) => (
          <li key={type}>{type}</li>
        ))}
      </ul>
    </aside>
  );
}
