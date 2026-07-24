// Wire types for the control-plane REST API, per
// specs/001-mergegate-control-plane/contracts/control-plane-api.md and
// data-model.md. Node/Edge/Attempt/Verdict internals belong to the tasks
// that own those areas (T019 canvas, T032 acceptance, T036 evidence); this
// client only needs the shapes it constructs requests from and passes
// responses through.

export interface Workflow {
  id: string;
  name: string;
  version?: string;
  nodes: unknown[];
  edges: unknown[];
  created_at?: string;
  updated_at?: string;
}

export type ContractMode = "user_defined" | "agent_generated" | "hybrid";

export type CriterionType =
  | "command"
  | "metric"
  | "openapi"
  | "git_policy"
  | "database_assertion"
  | "architecture";

export interface Criterion {
  id: string;
  type: CriterionType;
  priority: number;
  command?: string;
  expected_exit_code?: number;
  baseline_expected?: "pass" | "fail";
  result_expected?: "pass" | "fail";
  metric_path?: string;
  minimum?: number;
  params?: Record<string, unknown>;
}

export interface Contract {
  id: string;
  run_id: string;
  mode: ContractMode;
  criteria: Criterion[];
  approved: boolean;
  frozen_hash: string;
}

export interface Clarification {
  reason: string;
  conflicting_criteria: string[];
}

export interface Budget {
  max_attempts: number;
  max_wall_clock_s: number;
  max_model_calls: number;
}

export interface CostAccounting {
  tokens: number;
  model_calls: number;
  usd: number;
}

export interface Policy {
  protected_paths: string[];
  forbidden_diff_patterns: string[];
}

export type RunStatus =
  | "running"
  | "paused"
  | "awaiting_gate"
  | "SUCCESS"
  | "CLARIFICATION_REQUIRED"
  | "HUMAN_REJECTED"
  | "EXHAUSTED"
  | "NO_PROGRESS"
  | "TIMED_OUT"
  | "POLICY_BLOCKED"
  | "CANCELLED";

export interface Run {
  id: string;
  workflow_id: string;
  objective: string;
  repo_ref: string;
  provider?: string | null;
  model?: string | null;
  policy?: Policy;
  status: RunStatus;
  budgets: Budget;
  current_attempt: number;
  cost: CostAccounting;
  started_at?: string | null;
  ended_at?: string | null;
  clarification?: Clarification | null;
}

// Attempt/Verdict/LedgerEntry are read-mostly payloads whose full field set
// belongs to the tasks that produce them (T027 orchestrator, T032 acceptance,
// T009 ledger). The client passes them through as-received.
export type Attempt = Record<string, unknown>;
export type Verdict = Record<string, unknown>;
export type LedgerEntry = Record<string, unknown>;

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
  };
}
