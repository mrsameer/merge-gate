import { useEffect, useState } from "react";
import { createApiClient } from "../api";
import type { ApiClient } from "../api";
import "./EvidencePanel.css";

type EvidencePayload = {
  red_green_evidence: {
    baseline: string;
    result: string;
    verdict: string;
    test_hash: string;
    baseline_hash: string;
    result_hash: string;
  };
  verdict: { acceptance_hash: string; passed: boolean };
};

const defaultClient = createApiClient();

export function EvidencePanel({
  runId,
  runStatus,
  client = defaultClient,
}: {
  runId: string | null;
  runStatus?: string;
  client?: ApiClient;
}) {
  const [evidence, setEvidence] = useState<EvidencePayload | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) return;
    void client
      .getEvidence(runId)
      .then((payload) => setEvidence(payload as EvidencePayload))
      .catch(() => setEvidence(null));
  }, [client, runId, runStatus]);

  if (!runId || !evidence) return null;
  const proof = evidence.red_green_evidence;

  const replay = async () => {
    const replayed = await client.replayRun(runId);
    const matched =
      (replayed as { acceptance_hash?: string }).acceptance_hash ===
      evidence.verdict.acceptance_hash;
    setMessage(
      matched ? "Replay matched the recorded verdict." : "Replay mismatch.",
    );
  };

  return (
    <section className="evidence-panel" aria-label="Validator evidence">
      <h2>
        {proof.verdict === "VALID_PROOF" ? "VALID PROOF" : "INVALID PROOF"}
      </h2>
      <p>
        Baseline: <strong>{proof.baseline}</strong> → Result:{" "}
        <strong>{proof.result}</strong>
      </p>
      <dl>
        <dt>Test hash</dt>
        <dd>{proof.test_hash}</dd>
        <dt>Baseline hash</dt>
        <dd>{proof.baseline_hash}</dd>
        <dt>Result hash</dt>
        <dd>{proof.result_hash}</dd>
        <dt>Acceptance hash</dt>
        <dd>{evidence.verdict.acceptance_hash}</dd>
      </dl>
      <button type="button" onClick={() => void replay()}>
        Replay verdict
      </button>
      {message && <p role="status">{message}</p>}
    </section>
  );
}
