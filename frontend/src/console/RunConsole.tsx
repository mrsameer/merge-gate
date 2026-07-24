import { useRunStore } from "../state/runStore";

export function RunConsole() {
  const run = useRunStore((s) => s.run);
  const log = useRunStore((s) => s.log);
  const executeRun = useRunStore((s) => s.executeRun);
  const finalize = useRunStore((s) => s.finalize);

  return (
    <section>
      <h2>Run console</h2>
      <p>Status: {run?.status ?? "idle"}</p>
      <p>Attempt: {run?.current_attempt ?? 0}</p>
      <div>
        <button type="button" onClick={() => void executeRun()}>
          Start run
        </button>
        <button type="button" onClick={() => void finalize()}>
          Approve final gate
        </button>
      </div>
      <ol>
        {log.map((entry, index) => (
          <li key={`${entry}-${index}`}>{entry}</li>
        ))}
      </ol>
    </section>
  );
}
