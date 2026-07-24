// Node-library panel: the eight draggable node kinds (spec.md FR-026).
// Items support both accessible click-add and drag/drop-to-canvas authoring.

import type { DragEvent } from "react";
import type { NodeType } from "../canvas/types";
import { NODE_DRAG_MIME, WORKFLOW_NODE_TYPES } from "../canvas/nodeLibrary";
import { useAppStore } from "../state/store";

export interface NodeLibraryPanelProps {
  onAddNode?: (type: NodeType) => void;
}

export function NodeLibraryPanel({ onAddNode }: NodeLibraryPanelProps) {
  const addNode = useAppStore((state) => state.addNode);
  const add = onAddNode ?? addNode;

  const beginDrag = (event: DragEvent, type: NodeType) => {
    event.dataTransfer.setData(NODE_DRAG_MIME, type);
    event.dataTransfer.effectAllowed = "copy";
  };

  return (
    <aside
      className="node-library-panel"
      data-testid="node-library-panel"
      aria-label="Node library"
    >
      <h2>Node library</h2>
      <ul>
        {WORKFLOW_NODE_TYPES.map((type) => (
          <li
            key={type}
            draggable
            data-testid={`node-library-${type}`}
            onDragStart={(event) => beginDrag(event, type)}
          >
            <span>{type}</span>
            <button type="button" onClick={() => add(type)}>
              Add {type}
            </button>
          </li>
        ))}
      </ul>
    </aside>
  );
}
