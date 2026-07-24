import { Background, Controls, ReactFlow } from "@xyflow/react";
import "@xyflow/react/dist/style.css";

const nodes = [
  { id: "input", position: { x: 0, y: 0 }, data: { label: "Input" } },
  {
    id: "success_criteria",
    position: { x: 200, y: 0 },
    data: { label: "Success Criteria" },
  },
  {
    id: "execution",
    position: { x: 400, y: 0 },
    data: { label: "Execution" },
  },
  {
    id: "validation",
    position: { x: 600, y: 0 },
    data: { label: "Validation" },
  },
];

const edges = [
  { id: "e1", source: "input", target: "success_criteria" },
  { id: "e2", source: "success_criteria", target: "execution" },
  { id: "e3", source: "execution", target: "validation" },
];

export function LoopCanvas() {
  return (
    <div style={{ width: "100%", height: 320 }}>
      <ReactFlow nodes={nodes} edges={edges} fitView>
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  );
}
