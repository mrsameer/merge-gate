// Node inspector placeholder: shows only the selected node's relevant
// settings (spec.md FR-027). Selection wiring lands in T059.

export function InspectorPanel() {
  return (
    <aside
      className="inspector-panel"
      data-testid="inspector-panel"
      aria-label="Node inspector"
    >
      <p>Select a node to inspect its settings.</p>
    </aside>
  );
}
