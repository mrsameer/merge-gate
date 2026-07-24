import { useEffect, useState } from "react";
import { createApiClient } from "../api";
import type { ApiClient, EvidenceBundle } from "../api";
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
  const [evidence, setEvidence] = useState<
    EvidencePayload | EvidenceBundle | null
  >(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) return;
    void client
      .getEvidence(runId)
      .then((payload) => {
        setEvidence(payload as EvidencePayload | EvidenceBundle);
        setLoadError(null);
      })
      .catch(() => {
        setEvidence(null);
        setLoadError(
          "Evidence unavailable. No completed, verified bundle was returned.",
        );
      });
  }, [client, runId, runStatus]);

  if (!runId) return null;
  if (loadError) {
    return (
      <section className="evidence-panel" aria-label="Validator evidence">
        <p role="alert">{loadError}</p>
      </section>
    );
  }
  if (!evidence) return null;
  const proof = evidence.red_green_evidence;
  const bundle = "terminal_state" in evidence ? evidence : null;
  const recordedAcceptanceHash =
    "verdict" in evidence
      ? evidence.verdict.acceptance_hash
      : evidence.acceptance_hash;

  const replay = async () => {
    const replayed = await client.replayRun(runId);
    const matched =
      (replayed as { acceptance_hash?: string }).acceptance_hash ===
      recordedAcceptanceHash;
    setMessage(
      matched ? "Replay matched the recorded verdict." : "Replay mismatch.",
    );
  };

  const download = () => {
    if (!bundle) return;
    const blob = new Blob([JSON.stringify(bundle, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "evidence-bundle.json";
    anchor.click();
    URL.revokeObjectURL(url);
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
        <dd>{recordedAcceptanceHash}</dd>
      </dl>
      <button type="button" onClick={() => void replay()}>
        Replay verdict
      </button>
      {bundle && (
        <button type="button" onClick={download}>
          Download evidence-bundle.json
        </button>
      )}
      {message && <p role="status">{message}</p>}
    </section>
  );
}
