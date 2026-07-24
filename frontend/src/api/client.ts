export type RunStatus =
  | "awaiting_gate"
  | "running"
  | "awaiting_final_gate"
  | "SUCCESS";

export interface Criterion {
  id: string;
  type: string;
  priority: number;
  command?: string;
}

export interface Contract {
  id: string;
  run_id: string;
  criteria: Criterion[];
  approved: boolean;
  frozen_hash?: string | null;
}

export interface Run {
  id: string;
  workflow_id: string;
  objective: string;
  repo_ref: string;
  status: RunStatus;
  contract?: Contract | null;
  current_attempt: number;
  branch_ref?: string | null;
}

const API_BASE = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return (await response.json()) as T;
}

export async function createRun(objective: string): Promise<Run> {
  return request<Run>("/runs", {
    method: "POST",
    body: JSON.stringify({
      workflow_id: "default-four-role-loop",
      objective,
      repo_ref: "demo-repo",
    }),
  });
}

export async function generateCriteria(runId: string): Promise<Contract> {
  const body = await request<{ contract: Contract }>(
    `/runs/${runId}/criteria:generate`,
    { method: "POST", body: "{}" },
  );
  return body.contract;
}

export async function approveCriteria(runId: string): Promise<Contract> {
  const body = await request<{ contract: Contract }>(
    `/runs/${runId}/criteria:approve`,
    { method: "POST", body: "{}" },
  );
  return body.contract;
}

export async function startRun(runId: string): Promise<Run> {
  return request<Run>(`/runs/${runId}:start`, { method: "POST", body: "{}" });
}

export async function approveFinalGate(runId: string): Promise<Run> {
  return request<Run>(`/runs/${runId}/gate:approve`, {
    method: "POST",
    body: "{}",
  });
}

export async function getRun(runId: string): Promise<Run> {
  return request<Run>(`/runs/${runId}`);
}
