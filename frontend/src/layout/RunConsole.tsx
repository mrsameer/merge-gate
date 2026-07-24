// Collapsible run console (spec.md FR-033). Live timeline + click-to-inspect
// wiring lands in T030/T056.

export interface RunConsoleProps {
  collapsed: boolean;
  onToggle: () => void;
}

export function RunConsole({ collapsed, onToggle }: RunConsoleProps) {
  return (
    <section
      className="run-console"
      data-testid="run-console"
      data-collapsed={collapsed}
      aria-label="Run console"
    >
      <button type="button" onClick={onToggle} aria-expanded={!collapsed}>
        Run console
      </button>
      {!collapsed && (
        <div className="run-console__timeline">No run in progress.</div>
      )}
    </section>
  );
}
