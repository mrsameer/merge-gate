// T018 — REST client test for frontend/src/api/.
//
// contracts/control-plane-api.md is the wire contract between the React UI
// and the FastAPI control plane. This test drives the client against a
// mocked fetch to pin down request method/URL/body shape and the error
// envelope (`{ error: { code, message } }`) documented there, without a
// running backend.

import { describe, it, expect, vi } from "vitest";
import { createApiClient, ApiError } from "../../src/api/client";

function jsonResponse(body: unknown, init: { status?: number } = {}) {
  return new Response(JSON.stringify(body), {
    status: init.status ?? 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("createApiClient", () => {
  it("creates a workflow via POST /workflows", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        id: "wf-1",
        name: "MergeGate default loop",
        nodes: [],
        edges: [],
      }),
    );
    const client = createApiClient({ fetch: fetchMock });

    const workflow = await client.createWorkflow({
      name: "MergeGate default loop",
      template: "four_role_loop",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/workflows",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          name: "MergeGate default loop",
          template: "four_role_loop",
        }),
      }),
    );
    expect(workflow).toEqual({
      id: "wf-1",
      name: "MergeGate default loop",
      nodes: [],
      edges: [],
    });
  });

  it("fetches a run via GET /runs/{id}", async () => {
    const run = { id: "run-1", status: "awaiting_gate", current_attempt: 0 };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(run));
    const client = createApiClient({ fetch: fetchMock });

    const result = await client.getRun("run-1");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/runs/run-1",
      expect.objectContaining({ method: "GET" }),
    );
    expect(result).toEqual(run);
  });

  it("starts a run via POST /runs/{id}:start", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ id: "run-1", status: "running" }));
    const client = createApiClient({ fetch: fetchMock });

    await client.startRun("run-1");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/runs/run-1:start",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("issues a human gate decision via POST /runs/{id}/gate:{approve|reject}", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ id: "run-1", status: "SUCCESS" }));
    const client = createApiClient({ fetch: fetchMock });

    await client.decideGate("run-1", "final", "approve");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/runs/run-1/gate:approve",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ kind: "final" }),
      }),
    );
  });

  it("requests a replay via POST /runs/{id}/replay", async () => {
    const verdict = {
      passed: true,
      acceptance_hash: "abc",
      replay_of: "attempt-1",
    };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(verdict));
    const client = createApiClient({ fetch: fetchMock });

    const result = await client.replayRun("run-1");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/runs/run-1/replay",
      expect.objectContaining({ method: "POST" }),
    );
    expect(result).toEqual(verdict);
  });

  it("throws ApiError with the server's code and message on a non-OK response", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(
        {
          error: {
            code: "contract_not_approved",
            message: "Contract must be approved first",
          },
        },
        { status: 409 },
      ),
    );
    const client = createApiClient({ fetch: fetchMock });

    await expect(client.startRun("run-1")).rejects.toMatchObject({
      name: "ApiError",
      status: 409,
      code: "contract_not_approved",
      message: "Contract must be approved first",
    });
  });

  it("throws an ApiError instance", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        jsonResponse(
          { error: { code: "not_found", message: "no such run" } },
          { status: 404 },
        ),
      );
    const client = createApiClient({ fetch: fetchMock });

    await expect(client.getRun("missing")).rejects.toBeInstanceOf(ApiError);
  });

  it("honors a custom baseUrl", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ id: "run-1" }));
    const client = createApiClient({
      fetch: fetchMock,
      baseUrl: "http://localhost:8000/api",
    });

    await client.getRun("run-1");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/runs/run-1",
      expect.anything(),
    );
  });
});
