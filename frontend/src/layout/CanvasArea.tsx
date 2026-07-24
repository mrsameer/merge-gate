// Graph canvas area (spec.md FR-026b), rendering the default four-role loop
// read-only (T019). Node-library authoring (T058) and live run wiring (T030)
// build on top of this.

import { GraphCanvas } from "../canvas/GraphCanvas";
import {
  DEFAULT_WORKFLOW,
  DEFAULT_NODE_POSITIONS,
} from "../canvas/defaultWorkflow";
import { useAppStore } from "../state/store";

export function CanvasArea() {
  const selectNode = useAppStore((s) => s.selectNode);

  return (
    <main
      className="canvas-area"
      data-testid="canvas-area"
      aria-label="Workflow canvas"
    >
      <GraphCanvas
        workflow={DEFAULT_WORKFLOW}
        positions={DEFAULT_NODE_POSITIONS}
        onSelectNode={selectNode}
      />
    </main>
  );
}
