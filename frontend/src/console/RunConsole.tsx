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
      <p>
        Attempt: {run?.current_attempt ?? 0}
        {run?.attempts?.length ? ` / ${run.attempts.length} recorded` : ""}
      </p>
      {run?.undelivered_report ? (
        <p role="alert">{run.undelivered_report.message}</p>
      ) : null}
      <div>
        <button type="button" onClick={() => void executeRun()}>
          Start run
        </button>
        <button type="button" onClick={() => void finalize()}>
          Approve final gate
        </button>
      </div>
      {run?.attempts?.map((attempt) => (
        <details key={attempt.id} open={!!attempt.feedback}>
          <summary>
            Attempt {attempt.index}
            {attempt.verdict?.passed ? " — passed" : " — failed"}
          </summary>
          {attempt.feedback ? (
            <ul>
              <li>Criterion: {attempt.feedback.criterion}</li>
              <li>Command: {attempt.feedback.command}</li>
              <li>Exit code: {attempt.feedback.exit_code}</li>
              <li>Location: {attempt.feedback.first_failing_location}</li>
              <li>
                Signature: {attempt.feedback.failure_signature.slice(0, 12)}…
              </li>
            </ul>
          ) : null}
        </details>
      ))}
      <ol>
        {log.map((entry, index) => (
          <li key={`${entry}-${index}`}>{entry}</li>
        ))}
      </ol>
    </section>
  );
}
