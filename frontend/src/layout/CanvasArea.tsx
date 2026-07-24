// Graph canvas area (spec.md FR-026b), rendering the default four-role loop
// read-only (T019). Node-library authoring (T058) and live run wiring (T030)
// build on top of this.

import { useMemo } from "react";
import { GraphCanvas } from "../canvas/GraphCanvas";
import { useAppStore } from "../state/store";
import type { NodeStatus } from "../canvas/types";

export function CanvasArea() {
  const workflow = useAppStore((s) => s.workflow);
  const positions = useAppStore((s) => s.positions);
  const nodeStatuses = useAppStore((s) => s.nodeStatuses);
  const events = useAppStore((s) => s.events);
  const attempt = useAppStore((s) => s.run?.current_attempt);
  const selectNode = useAppStore((s) => s.selectNode);
  const moveNode = useAppStore((s) => s.moveNode);
  const connectNodes = useAppStore((s) => s.connectNodes);
  const addNode = useAppStore((s) => s.addNode);
  const renderedWorkflow = useMemo(() => {
    const latestVerdict = [...events]
      .reverse()
      .find((event) => event.type === "verdict");
    return {
      ...workflow,
      nodes: workflow.nodes.map((node) => {
        const statusKey = node.id === "validator" ? "validation" : node.id;
        const status = nodeStatuses[statusKey] as NodeStatus | undefined;
        const latestResult =
          node.id === "validator" && latestVerdict
            ? latestVerdict.data.passed
              ? "Validation passed"
              : "Validation failed"
            : undefined;
        return {
          ...node,
          status: status ?? node.status,
          ...(status && attempt ? { attemptNumber: attempt } : {}),
          ...(latestResult ? { latestResult } : {}),
        };
      }),
    };
  }, [attempt, events, nodeStatuses, workflow]);

  return (
    <main
      className="canvas-area"
      data-testid="canvas-area"
      aria-label="Workflow canvas"
    >
      <GraphCanvas
        workflow={renderedWorkflow}
        positions={positions}
        onSelectNode={selectNode}
        onMoveNode={moveNode}
        onConnectNodes={connectNodes}
        onDropNode={addNode}
      />
    </main>
  );
}
