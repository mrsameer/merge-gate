// REST client for the FastAPI control plane, per
// specs/001-mergegate-control-plane/contracts/control-plane-api.md.

import type {
  ApiErrorBody,
  Attempt,
  Budget,
  Clarification,
  Contract,
  ContractMode,
  Criterion,
  LedgerEntry,
  Run,
  Verdict,
  Workflow,
} from "./types";

const DEFAULT_BASE_URL = "/api";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export interface ApiClientOptions {
  baseUrl?: string;
  fetch?: typeof fetch;
}

async function request<T>(
  path: string,
  init: RequestInit,
  options: ApiClientOptions,
): Promise<T> {
  const baseUrl = options.baseUrl ?? DEFAULT_BASE_URL;
  const fetchImpl = options.fetch ?? globalThis.fetch;

  const response = await fetchImpl(`${baseUrl}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init.headers },
  });

  const body = response.status === 204 ? null : await response.json();

  if (!response.ok) {
    const errorBody = body as ApiErrorBody | null;
    throw new ApiError(
      response.status,
      errorBody?.error?.code ?? "unknown_error",
      errorBody?.error?.message ?? response.statusText,
    );
  }

  return body as T;
}

export function createApiClient(options: ApiClientOptions = {}) {
  const call = <T>(path: string, init: RequestInit = {}) =>
    request<T>(path, { method: "GET", ...init }, options);

  return {
    createWorkflow: (body: { name: string; template?: string }) =>
      call<Workflow>("/workflows", {
        method: "POST",
        body: JSON.stringify(body),
      }),

    getWorkflow: (id: string) => call<Workflow>(`/workflows/${id}`),

    updateWorkflow: (id: string, body: Partial<Workflow>) =>
      call<Workflow>(`/workflows/${id}`, {
        method: "PUT",
        body: JSON.stringify(body),
      }),

    exportWorkflow: (id: string, format: "yaml" | "json" = "json") =>
      call<unknown>(`/workflows/${id}/export?format=${format}`, {
        method: "POST",
      }),

    importWorkflow: (payload: unknown) =>
      call<Workflow>("/workflows/import", {
        method: "POST",
        body: JSON.stringify(payload),
      }),

    generateCriteria: (runId: string, mode: ContractMode = "hybrid") =>
      call<Contract | { clarification: Clarification }>(
        `/runs/${runId}/criteria:generate`,
        { method: "POST", body: JSON.stringify({ mode }) },
      ),

    updateCriteria: (runId: string, criteria: Criterion[]) =>
      call<Contract>(`/runs/${runId}/criteria`, {
        method: "PUT",
        body: JSON.stringify({ criteria }),
      }),

    approveCriteria: (runId: string) =>
      call<Contract>(`/runs/${runId}/criteria:approve`, { method: "POST" }),

    createRun: (body: {
      workflow_id: string;
      objective: string;
      repo_ref: string;
      provider?: string;
      model?: string;
      budgets: Budget;
    }) => call<Run>("/runs", { method: "POST", body: JSON.stringify(body) }),

    getRun: (id: string) => call<Run>(`/runs/${id}`),

    startRun: (id: string) =>
      call<Run>(`/runs/${id}:start`, { method: "POST" }),
    pauseRun: (id: string) =>
      call<Run>(`/runs/${id}:pause`, { method: "POST" }),
    resumeRun: (id: string) =>
      call<Run>(`/runs/${id}:resume`, { method: "POST" }),
    stopRun: (id: string) => call<Run>(`/runs/${id}:stop`, { method: "POST" }),

    decideGate: (
      id: string,
      kind: "contract" | "final",
      decision: "approve" | "reject",
    ) =>
      call<Run>(`/runs/${id}/gate:${decision}`, {
        method: "POST",
        body: JSON.stringify({ kind }),
      }),

    listAttempts: (runId: string) => call<Attempt[]>(`/runs/${runId}/attempts`),
    getAttempt: (runId: string, index: number) =>
      call<Attempt>(`/runs/${runId}/attempts/${index}`),
    getLedger: (runId: string) => call<LedgerEntry[]>(`/runs/${runId}/ledger`),
    getEvidence: (runId: string) => call<unknown>(`/runs/${runId}/evidence`),
    replayRun: (runId: string) =>
      call<Verdict>(`/runs/${runId}/replay`, { method: "POST" }),
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;
