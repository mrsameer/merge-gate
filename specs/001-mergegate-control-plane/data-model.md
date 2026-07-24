# Phase 1 Data Model: MergeGate

**Feature**: 001-mergegate-control-plane | **Date**: 2026-07-24

Entities derived from the spec's Key Entities and Functional Requirements. Field types are
language-agnostic; the backend realizes these as Pydantic models and SQLite tables.

## Workflow

The typed-node graph; its default form is the four-role loop. Serializable to YAML/JSON.

| Field | Type | Notes |
|-------|------|-------|
| id | string (uuid) | |
| name | string | Shown in top bar |
| version | string | For reusable/versioned templates (bonus) |
| nodes | Node[] | See Node |
| edges | Edge[] | Directed; carry a path label |
| created_at / updated_at | timestamp | |

**Validation**: exactly one `Input` node; ≥1 `Success` and ≥1 `Stop`; every non-terminal node has a
defined success path and (where applicable) failure path (FR-028); graph must be re-importable to an
identical structure (FR-028a, SC-014).

### Node

| Field | Type | Notes |
|-------|------|-------|
| id | string | |
| type | enum | `Input, Agent, Command, Validator, Decision, HumanGate, Success, Stop` |
| name | string | |
| config | NodeConfig | Only fields relevant to `type` are used (FR-027) |
| status | enum | `idle, running, passed, failed, blocked, waiting, skipped` (runtime) |
| latest_result | ResultSummary? | Runtime; shown on the node |

**NodeConfig** (union by type): `instructions`, `role` (`success_criteria|planning|execution|validation`),
`model`/`provider`, `tools[]`, `command`, `timeout_s`, `criteria_ref`, `retry_limit`, `success_path`,
`failure_path`, `completion_condition`. Drives per-node configurability (FR-031).

### Edge

| Field | Type | Notes |
|-------|------|-------|
| id | string | |
| source / target | node id | |
| path | enum | `default, success, failure` (FR-026a) |

## Agent Role

One of the four default-loop roles, each configurable independently.

| Field | Type | Notes |
|-------|------|-------|
| role | enum | `success_criteria, planning, execution, validation` |
| instructions | string | Editable (FR-031) |
| provider / model | string | Selected via config; not hardcoded (FR-034) |
| tools | string[] | Tools available to this role |

> The **validation** role is realized by the deterministic acceptance engine, not an LLM (Principle I).

## Contract / Criteria

Frozen, human-approved acceptance criteria (FR-002/FR-003).

| Field | Type | Notes |
|-------|------|-------|
| id | string | |
| run_id | string | |
| mode | enum | `user_defined, agent_generated, hybrid` (default hybrid) (FR-001a) |
| criteria | Criterion[] | Ordered by priority (FR-001b) |
| approved | bool | Must be true before execution |
| frozen_hash | string | Hash of approved criteria set |

### Criterion

| Field | Type | Notes |
|-------|------|-------|
| id | string | e.g., `task-tests`, `coverage`, `protected-files` |
| type | enum | `command, metric, openapi, git_policy, database_assertion, architecture` (FR-001c) |
| priority | int | Lower = higher priority |
| command | string? | For command/metric types |
| expected_exit_code | int? | |
| baseline_expected | enum? | `pass, fail` — drives red-before/green-after (FR-009) |
| result_expected | enum? | `pass, fail` |
| metric_path / minimum | string / number? | For metric type (e.g., coverage) |
| params | object? | Type-specific (protected paths, required headers, response codes) |

## Run

A single execution of a workflow against an objective.

| Field | Type | Notes |
|-------|------|-------|
| id | string | |
| workflow_id | string | |
| objective | string | Plain-language input |
| repo_ref | string | Target repository + base commit |
| status | enum | Terminal states (FR-025): `SUCCESS, CLARIFICATION_REQUIRED, HUMAN_REJECTED, EXHAUSTED, NO_PROGRESS, TIMED_OUT, POLICY_BLOCKED, CANCELLED`; plus non-terminal `running, paused, awaiting_gate` |
| budgets | Budget | `max_attempts, max_wall_clock_s, max_model_calls` (FR-013) |
| attempts | Attempt[] | |
| current_attempt | int | Attempt counter shown in top bar |
| cost | CostAccounting | tokens, model_calls, usd (FR-022) |
| started_at / ended_at | timestamp | |

**State transitions**: `running → awaiting_gate → running` (human gates); `running → paused → running`
(operator); any → a terminal state. An exception/timeout MUST map to `TIMED_OUT`/`NO_PROGRESS`/a safe
stop — never `SUCCESS` (Principle IV).

## Attempt

One iteration within a run, bound to an isolated workspace.

| Field | Type | Notes |
|-------|------|-------|
| id | string | |
| run_id | string | |
| index | int | 1-based |
| worktree_path | string | Disposable git worktree (FR-011) |
| branch | string | Per-attempt feature branch |
| diff | string | Captured `git diff` |
| changed_files | string[] | |
| harness_log | string | stdout/stderr from the provider |
| verdict | Verdict | |
| failure_signature | string? | For no-progress detection (FR-014) |
| feedback | StructuredFeedback? | Fed to next Planning attempt (FR-012) |

### StructuredFeedback

`{ criterion, command, exit_code, failure_signature, first_failing_location, attempt }` (FR-012).

## Verdict

Deterministic pass/fail for an attempt (Principle I/II).

| Field | Type | Notes |
|-------|------|-------|
| attempt_id | string | |
| passed | bool | Computed only by the acceptance engine |
| checks | CheckResult[] | Ordered pipeline results |
| acceptance_hash | string | Hash of the acceptance input |
| acceptance_input | object | `{commit_sha, validation_config, tool_versions, env_fingerprint}` (FR-010) |
| replay_of | string? | Set when produced by a replay run |

### CheckResult

| Field | Type | Notes |
|-------|------|-------|
| criterion_id | string | |
| step | enum | `build, lint, existing_tests, new_tests, migration, coverage, api_contract, policy` |
| passed | bool | |
| exit_code | int | |
| stdout / stderr | string | Captured (FR-007) |
| duration_ms | int | |
| baseline_result | enum? | `pass, fail` for red-before/green-after (FR-009) |

## Policy

Anti-cheat configuration (FR-017/FR-018).

| Field | Type | Notes |
|-------|------|-------|
| protected_paths | glob[] | e.g., `app/auth/**`, `tests/acceptance/**` |
| forbidden_diff_patterns | string[] | e.g., `pytest.mark.skip`, `eslint-disable` |

A violation produces a `POLICY_BLOCKED` verdict naming the offending path/pattern.

## LedgerEntry

Append-only, hash-chained event (Principle III, FR-019).

| Field | Type | Notes |
|-------|------|-------|
| seq | int | Monotonic |
| run_id | string | |
| ts | timestamp | |
| type | enum | `objective, contract, plan, harness, command, verdict, retry, gate, policy, terminal, replay` |
| payload | object | Event-specific |
| prev_hash | string | Hash of previous entry |
| hash | string | `H(prev_hash + canonical(payload))` |

## EvidenceBundle

Exported proof-carrying record (FR-020). Assembled from the ledger.

Contains: `contract`, `plan`, `diff`, `commands[]` (with exit codes), `red_green_evidence`,
`policy_results`, `retries[]`, `acceptance_hash`, `cost`, `time`, `terminal_state`, and the full
`ledger[]` for hash-chain verification. Schema: [contracts/evidence-bundle.schema.json](contracts/evidence-bundle.schema.json).

## ProviderAdapter (interface, not stored)

`propose_changes(objective, feedback, workspace) -> { diff, changed_files, log, tokens, model_calls, usd }`.
Selected via config; swappable without changing the workflow (FR-034/FR-035).
