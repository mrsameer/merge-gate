import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { EvidencePanel } from "../../src/evidence/EvidencePanel";
import type { ApiClient } from "../../src/api";

const evidence = {
  red_green_evidence: {
    baseline: "FAILED",
    result: "PASSED",
    verdict: "VALID_PROOF",
    test_hash: "test-hash",
    baseline_hash: "baseline-hash",
    result_hash: "result-hash",
  },
  verdict: { acceptance_hash: "acceptance-hash", passed: true },
};

const bundle = {
  run_id: "run-1",
  terminal_state: "SUCCESS",
  ...evidence,
  acceptance_hash: "acceptance-hash",
  contract: { mode: "hybrid", criteria: [], frozen_hash: "frozen" },
  plan: "plan",
  diff: "+proof",
  commands: [],
  policy_results: [],
  retries: [],
  cost: { tokens: 1, model_calls: 1, usd: 0.01 },
  time: {
    started_at: "2026-07-24T10:00:00Z",
    ended_at: "2026-07-24T10:00:01Z",
    wall_clock_s: 1,
  },
  ledger: [],
};

describe("EvidencePanel", () => {
  it("does not request evidence before an execution attempt exists", () => {
    const getEvidence = vi.fn().mockResolvedValue(evidence);

    render(
      <EvidencePanel
        runId="run-1"
        runStatus="awaiting_gate"
        currentAttempt={0}
        client={{ getEvidence } as unknown as ApiClient}
      />,
    );

    expect(getEvidence).not.toHaveBeenCalled();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("does not request evidence while an attempt has no verdict", () => {
    const getEvidence = vi.fn().mockResolvedValue(evidence);

    render(
      <EvidencePanel
        runId="run-1"
        runStatus="running"
        currentAttempt={1}
        hasCompletedVerdict={false}
        client={{ getEvidence } as unknown as ApiClient}
      />,
    );

    expect(getEvidence).not.toHaveBeenCalled();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("renders proof hashes and replays the completed verdict", async () => {
    const getEvidence = vi.fn().mockResolvedValue(evidence);
    const replayRun = vi.fn().mockResolvedValue({
      acceptance_hash: "acceptance-hash",
      replay_of: "attempt-1",
      passed: true,
    });
    render(
      <EvidencePanel
        runId="run-1"
        runStatus="awaiting_gate"
        client={{ getEvidence, replayRun } as unknown as ApiClient}
      />,
    );

    expect(await screen.findByText("VALID PROOF")).toBeInTheDocument();
    expect(screen.getByText("baseline-hash")).toBeInTheDocument();
    expect(screen.getByText("result-hash")).toBeInTheDocument();
    expect(screen.getByText("acceptance-hash")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /replay verdict/i }));
    await waitFor(() => expect(replayRun).toHaveBeenCalledWith("run-1"));
    expect(await screen.findByText(/replay matched/i)).toBeInTheDocument();
  });

  it("refetches evidence when the active run reaches a new status", async () => {
    const getEvidence = vi
      .fn()
      .mockRejectedValueOnce(new Error("not ready"))
      .mockResolvedValueOnce(evidence);
    const { rerender } = render(
      <EvidencePanel
        runId="run-1"
        runStatus="running"
        client={{ getEvidence } as unknown as ApiClient}
      />,
    );

    await waitFor(() => expect(getEvidence).toHaveBeenCalledTimes(1));
    rerender(
      <EvidencePanel
        runId="run-1"
        runStatus="awaiting_gate"
        client={{ getEvidence } as unknown as ApiClient}
      />,
    );

    expect(await screen.findByText("VALID PROOF")).toBeInTheDocument();
    expect(getEvidence).toHaveBeenCalledTimes(2);
  });

  it("downloads the completed evidence bundle with the canonical filename", async () => {
    const getEvidence = vi.fn().mockResolvedValue(bundle);
    const createObjectURL = vi.fn().mockReturnValue("blob:evidence");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", { createObjectURL, revokeObjectURL });
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => {});

    render(
      <EvidencePanel
        runId="run-1"
        runStatus="SUCCESS"
        client={{ getEvidence } as unknown as ApiClient}
      />,
    );

    fireEvent.click(
      await screen.findByRole("button", { name: /download evidence/i }),
    );

    expect(createObjectURL).toHaveBeenCalledOnce();
    expect(click).toHaveBeenCalledOnce();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:evidence");
  });

  it("reports evidence loading failures truthfully", async () => {
    render(
      <EvidencePanel
        runId="run-1"
        runStatus="SUCCESS"
        client={
          {
            getEvidence: vi.fn().mockRejectedValue(new Error("bundle invalid")),
          } as unknown as ApiClient
        }
      />,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Evidence unavailable",
    );
    expect(
      screen.queryByRole("button", { name: /download evidence/i }),
    ).not.toBeInTheDocument();
  });

  it("reports a replay mismatch instead of claiming the proof matched", async () => {
    const replayRun = vi
      .fn()
      .mockResolvedValue({ acceptance_hash: "different-hash", passed: true });
    render(
      <EvidencePanel
        runId="run-1"
        runStatus="SUCCESS"
        client={
          {
            getEvidence: vi.fn().mockResolvedValue(evidence),
            replayRun,
          } as unknown as ApiClient
        }
      />,
    );

    fireEvent.click(
      await screen.findByRole("button", { name: /replay verdict/i }),
    );

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Replay mismatch",
    );
    expect(screen.queryByText(/replay matched/i)).not.toBeInTheDocument();
  });

  it("reports replay failures truthfully without replacing the recorded proof", async () => {
    const replayRun = vi
      .fn()
      .mockRejectedValue(new Error("replay service unavailable"));
    render(
      <EvidencePanel
        runId="run-1"
        runStatus="SUCCESS"
        client={
          {
            getEvidence: vi.fn().mockResolvedValue(evidence),
            replayRun,
          } as unknown as ApiClient
        }
      />,
    );

    fireEvent.click(
      await screen.findByRole("button", { name: /replay verdict/i }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Replay failed: replay service unavailable",
    );
    expect(screen.getByText("VALID PROOF")).toBeInTheDocument();
  });

  it("does not show the previous run's proof while new evidence is loading", async () => {
    let resolveSecond: ((payload: typeof evidence) => void) | undefined;
    const getEvidence = vi
      .fn()
      .mockResolvedValueOnce(evidence)
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveSecond = resolve;
          }),
      );
    const client = { getEvidence } as unknown as ApiClient;
    const { rerender } = render(
      <EvidencePanel runId="run-1" runStatus="SUCCESS" client={client} />,
    );
    expect(await screen.findByText("acceptance-hash")).toBeInTheDocument();

    rerender(
      <EvidencePanel runId="run-2" runStatus="running" client={client} />,
    );
    await waitFor(() => expect(getEvidence).toHaveBeenCalledWith("run-2"));

    expect(screen.queryByText("acceptance-hash")).not.toBeInTheDocument();
    expect(screen.queryByText("VALID PROOF")).not.toBeInTheDocument();

    resolveSecond?.(evidence);
  });
});
