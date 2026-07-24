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

describe("EvidencePanel", () => {
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
});
