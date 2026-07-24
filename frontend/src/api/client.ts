export type RunStatus =
  | "awaiting_gate"
  | "running"
  | "awaiting_final_gate"
  | "SUCCESS"
  | "EXHAUSTED"
  | "NO_PROGRESS"
  | "CLARIFICATION_REQUIRED"
  | "POLICY_BLOCKED";

export interface Policy {
  protected_paths: string[];
  forbidden_diff_patterns: string[];
}

export interface PolicyViolation {
  kind: string;
  offender: string;
  message: string;
}

export interface ClarificationConflict {
  kind: string;
  criteria_ids: string[];
  detail: string;
}

export interface ClarificationRequest {
  reason: string;
  message: string;
  conflicts: ClarificationConflict[];
  objective: string;
}

export interface StructuredFeedback {
  criterion: string;
  command: string;
  exit_code: number;
  failure_signature: string;
  first_failing_location: string;
  attempt: number;
}

export interface UndeliveredReport {
  delivered: boolean;
  reason: string;
  attempts: number;
  message: string;
}

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

export interface RedGreenEvidence {
  criterion_id: string;
  baseline: string;
  result: string;
  verdict: string;
  test_hash: string;
  baseline_hash: string;
  result_hash: string;
  baseline_exit_code: number;
  result_exit_code: number;
  command?: string;
}

export interface Verdict {
  passed: boolean;
  acceptance_hash: string;
  replay_of?: string | null;
}

export interface Attempt {
  id: string;
  index: number;
  verdict?: Verdict | null;
  evidence?: RedGreenEvidence | null;
  feedback?: StructuredFeedback | null;
  failure_signature?: string | null;
  policy_violation?: PolicyViolation | null;
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
  attempts?: Attempt[];
  cost?: { model_calls: number };
  undelivered_report?: UndeliveredReport | null;
  clarification_request?: ClarificationRequest | null;
  policy?: Policy;
  policy_violation?: PolicyViolation | null;
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

export const DEFAULT_POLICY: Policy = {
  protected_paths: ["app/auth/**"],
  forbidden_diff_patterns: [
    "pytest.mark.skip",
    "@pytest.mark.skip",
    "pytest.skip(",
  ],
};

export async function createRun(
  objective: string,
  policy: Policy = DEFAULT_POLICY,
): Promise<Run> {
  return request<Run>("/runs", {
    method: "POST",
    body: JSON.stringify({
      workflow_id: "default-four-role-loop",
      objective,
      repo_ref: "demo-repo",
      policy,
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

export async function replayValidation(runId: string): Promise<Verdict> {
  return request<Verdict>(`/runs/${runId}/replay`, {
    method: "POST",
    body: "{}",
  });
}
