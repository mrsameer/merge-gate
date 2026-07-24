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
  const [evidenceState, setEvidenceState] = useState<{
    runId: string;
    payload: EvidencePayload | EvidenceBundle | null;
    error: string | null;
  }>({ runId: "", payload: null, error: null });
  const [replayState, setReplayState] = useState<{
    runId: string;
    message: string | null;
    error: string | null;
    pending: boolean;
  }>({ runId: "", message: null, error: null, pending: false });

  useEffect(() => {
    if (!runId) return;
    let active = true;
    void client
      .getEvidence(runId)
      .then((payload) => {
        if (!active) return;
        setEvidenceState({
          runId,
          payload: payload as EvidencePayload | EvidenceBundle,
          error: null,
        });
      })
      .catch(() => {
        if (!active) return;
        setEvidenceState({
          runId,
          payload: null,
          error:
            "Evidence unavailable. No completed, verified bundle was returned.",
        });
      });
    return () => {
      active = false;
    };
  }, [client, runId, runStatus]);

  if (!runId) return null;
  const evidence = evidenceState.runId === runId ? evidenceState.payload : null;
  const loadError = evidenceState.runId === runId ? evidenceState.error : null;
  const message = replayState.runId === runId ? replayState.message : null;
  const replayError = replayState.runId === runId ? replayState.error : null;
  const replaying = replayState.runId === runId ? replayState.pending : false;
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
    setReplayState({
      runId,
      message: null,
      error: null,
      pending: true,
    });
    try {
      const replayed = await client.replayRun(runId);
      const matched =
        (replayed as { acceptance_hash?: string }).acceptance_hash ===
        recordedAcceptanceHash;
      setReplayState({
        runId,
        message: matched
          ? "Replay matched the recorded verdict."
          : "Replay mismatch.",
        error: null,
        pending: false,
      });
    } catch (error) {
      setReplayState({
        runId,
        message: null,
        error: `Replay failed: ${
          error instanceof Error ? error.message : String(error)
        }`,
        pending: false,
      });
    }
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
      <button type="button" onClick={() => void replay()} disabled={replaying}>
        {replaying ? "Replaying verdict…" : "Replay verdict"}
      </button>
      {bundle && (
        <button type="button" onClick={download}>
          Download evidence-bundle.json
        </button>
      )}
      {message && <p role="status">{message}</p>}
      {replayError && <p role="alert">{replayError}</p>}
    </section>
  );
}
