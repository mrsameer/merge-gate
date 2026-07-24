import { useRunStore } from "../state/runStore";

export function InspectorPanel() {
  const objective = useRunStore((s) => s.objective);
  const contract = useRunStore((s) => s.contract);
  const policy = useRunStore((s) => s.policy);
  const setObjective = useRunStore((s) => s.setObjective);
  const setPolicy = useRunStore((s) => s.setPolicy);
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
      <h3>Policy</h3>
      <label htmlFor="protected-paths">Protected paths (one per line)</label>
      <textarea
        id="protected-paths"
        value={policy.protected_paths.join("\n")}
        onChange={(event) =>
          setPolicy({
            ...policy,
            protected_paths: event.target.value
              .split("\n")
              .map((line) => line.trim())
              .filter(Boolean),
          })
        }
        rows={3}
      />
      <label htmlFor="forbidden-patterns">Forbidden diff patterns (one per line)</label>
      <textarea
        id="forbidden-patterns"
        value={policy.forbidden_diff_patterns.join("\n")}
        onChange={(event) =>
          setPolicy({
            ...policy,
            forbidden_diff_patterns: event.target.value
              .split("\n")
              .map((line) => line.trim())
              .filter(Boolean),
          })
        }
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
