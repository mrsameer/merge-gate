import { useRunStore } from "../state/runStore";
import { replayValidation } from "../api/client";

export function EvidencePanel() {
  const run = useRunStore((s) => s.run);
  const replayLog = useRunStore((s) => s.replayLog);
  const setReplayLog = useRunStore((s) => s.setReplayLog);

  const attempt = run?.attempts?.[run.attempts.length - 1];
  const evidence = attempt?.evidence;

  if (!evidence) {
    return (
      <section>
        <h2>Evidence</h2>
        <p>No red→green evidence yet. Complete a run to inspect proof.</p>
      </section>
    );
  }

  return (
    <section>
      <h2>Evidence</h2>
      <dl>
        <dt>Baseline</dt>
        <dd>{evidence.baseline} as expected</dd>
        <dt>Result</dt>
        <dd>{evidence.result}</dd>
        <dt>Verdict</dt>
        <dd>{evidence.verdict}</dd>
        <dt>Test hash</dt>
        <dd>
          <code>{evidence.test_hash.slice(0, 12)}…</code>
        </dd>
        <dt>Baseline hash</dt>
        <dd>
          <code>{evidence.baseline_hash.slice(0, 12)}…</code>
        </dd>
        <dt>Result hash</dt>
        <dd>
          <code>{evidence.result_hash.slice(0, 12)}…</code>
        </dd>
        <dt>Acceptance hash</dt>
        <dd>
          <code>{attempt?.verdict?.acceptance_hash?.slice(0, 12)}…</code>
        </dd>
      </dl>
      <button
        type="button"
        onClick={() => {
          if (!run) return;
          void replayValidation(run.id).then((verdict) => {
            setReplayLog(
              `Replay acceptance_hash=${verdict.acceptance_hash.slice(0, 12)}… (zero model calls)`,
            );
          });
        }}
      >
        Replay validation
      </button>
      {replayLog ? <p>{replayLog}</p> : null}
    </section>
  );
}
