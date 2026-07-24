import { useRunStore } from "../state/runStore";

export function InspectorPanel() {
  const objective = useRunStore((s) => s.objective);
  const contract = useRunStore((s) => s.contract);
  const setObjective = useRunStore((s) => s.setObjective);
  const submitObjective = useRunStore((s) => s.submitObjective);
  const generateAndApprove = useRunStore((s) => s.generateAndApprove);

  return (
    <section>
      <h2>Inspector</h2>
      <label htmlFor="objective">Objective</label>
      <textarea
        id="objective"
        value={objective}
        onChange={(event) => setObjective(event.target.value)}
        rows={4}
      />
      <div>
        <button type="button" onClick={() => void submitObjective()}>
          Submit objective
        </button>
        <button type="button" onClick={() => void generateAndApprove()}>
          Generate &amp; approve contract
        </button>
      </div>
      {contract ? (
        <ul>
          {contract.criteria.map((criterion) => (
            <li key={criterion.id}>
              {criterion.id} — {criterion.command ?? criterion.type}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
