// Top bar: workflow name, save/export, run/pause/stop, status, attempt
// counter (spec.md FR-026b). Wiring to the run API lands in T062.

export function TopBar() {
  return (
    <header className="top-bar" data-testid="top-bar">
      <span className="top-bar__workflow-name">MergeGate default loop</span>
      <div className="top-bar__controls">
        <button type="button" disabled>
          Save
        </button>
        <button type="button" disabled>
          Export
        </button>
        <button type="button" disabled>
          Run
        </button>
        <button type="button" disabled>
          Pause
        </button>
        <button type="button" disabled>
          Stop
        </button>
      </div>
      <span className="top-bar__status" data-testid="run-status">
        idle
      </span>
      <span className="top-bar__attempt-counter" data-testid="attempt-counter">
        Attempt 0
      </span>
    </header>
  );
}
