# Contract: Control Plane API (REST + SSE)

**Feature**: 001-mergegate-control-plane | **Date**: 2026-07-24

Base URL: `/api`. All bodies are JSON unless noted. Errors use `{ "error": { "code", "message" } }`
with standard HTTP status codes. This contract is the interface between the React Flow UI and the
FastAPI control plane.

## Workflows

| Method | Path | Purpose | Maps to |
|--------|------|---------|---------|
| `POST` | `/workflows` | Create a workflow (default = four-role loop) | FR-026, FR-031 |
| `GET` | `/workflows/{id}` | Fetch a workflow graph | FR-026 |
| `PUT` | `/workflows/{id}` | Update nodes/edges/config | FR-026a, FR-027, FR-031 |
| `POST` | `/workflows/{id}/export` | Export as YAML or JSON (`?format=yaml\|json`) | FR-028, FR-028a |
| `POST` | `/workflows/import` | Import YAML/JSON → workflow; reruns identically | FR-028a, SC-014 |

`POST /workflows` request:
```json
{ "name": "MergeGate default loop", "template": "four_role_loop" }
```
Response `201`: full `Workflow` (see [workflow.schema.json](workflow.schema.json)).

## Success criteria (contract)

| Method | Path | Purpose | Maps to |
|--------|------|---------|---------|
| `POST` | `/runs/{run_id}/criteria:generate` | Hybrid/agent generation from objective + repo map | FR-001, FR-001a |
| `PUT` | `/runs/{run_id}/criteria` | Edit/prioritize criteria before approval | FR-001b |
| `POST` | `/runs/{run_id}/criteria:approve` | Freeze the contract | FR-002, FR-003 |

`POST /criteria:generate` request: `{ "mode": "hybrid" }` → `Contract`. If criteria are contradictory,
the run transitions to `CLARIFICATION_REQUIRED` and the response includes a `clarification` object
(FR-016) instead of an approvable contract.

## Runs & control

| Method | Path | Purpose | Maps to |
|--------|------|---------|---------|
| `POST` | `/runs` | Create a run `{ workflow_id, objective, repo_ref, budgets }` | US1, FR-013 |
| `GET` | `/runs/{id}` | Run status, current attempt, cost, terminal state | FR-022, FR-025 |
| `POST` | `/runs/{id}:start` | Begin execution (after contract approved) | US1 |
| `POST` | `/runs/{id}:pause` | Pause | FR-023 |
| `POST` | `/runs/{id}:resume` | Resume | FR-023 |
| `POST` | `/runs/{id}:stop` | Manual stop → `CANCELLED` | FR-023, FR-025 |
| `POST` | `/runs/{id}/gate:{approve\|reject}` | Human gate decision (contract / final merge) | FR-024 |

`POST /runs` response `201`: `Run` with `status: "awaiting_gate"` (contract gate) and
`current_attempt: 0`.

Human gate: `reject` on the final gate → `HUMAN_REJECTED`; `approve` on the final gate → `SUCCESS`
with the resulting branch/patch reference.

## Attempts, verdict, evidence

| Method | Path | Purpose | Maps to |
|--------|------|---------|---------|
| `GET` | `/runs/{id}/attempts` | List attempts (diff, changed files, verdict, feedback) | FR-032 |
| `GET` | `/runs/{id}/attempts/{n}` | Inspect one attempt (agent input/output, commands, files) | FR-032, FR-033 |
| `GET` | `/runs/{id}/ledger` | Full hash-chained ledger (timeline) | FR-019, FR-021 |
| `GET` | `/runs/{id}/evidence` | Download `evidence-bundle.json` | FR-020 |
| `POST` | `/runs/{id}/replay` | Re-compute verdict from recorded state, **zero model calls** | FR-010, SC-001 |

`POST /replay` response: a `Verdict` with `replay_of` set; MUST equal the original verdict
(`acceptance_hash` identical). Server MUST guarantee the provider adapter is disabled during replay.

## SSE event stream

`GET /runs/{id}/events` → `text/event-stream`. Reconnectable via `Last-Event-ID` (browser refresh
edge case, SC-011 #9). Event `data` is a `LedgerEntry`-shaped JSON object:

```text
event: node_status      # {node_id, status, attempt}
event: harness_output   # {attempt, chunk}            (optional live streaming, bonus)
event: command_result   # {criterion_id, step, exit_code, duration_ms}
event: verdict          # {attempt, passed, acceptance_hash}
event: retry            # {attempt, failure_signature, feedback}
event: gate             # {kind: "contract"|"final", state: "awaiting"}
event: policy_block     # {path_or_pattern}
event: terminal         # {state}
```

## Contract test expectations (for `backend/tests/contract/`)

- Creating a run before contract approval and calling `:start` MUST fail (409) — contract-before-code.
- `:start` with a contradictory contract MUST yield `CLARIFICATION_REQUIRED` and MUST NOT create an
  attempt.
- `/replay` MUST return a verdict whose `acceptance_hash` equals the original and MUST record zero
  model calls in cost accounting.
- A diff touching a protected path MUST yield `POLICY_BLOCKED` naming the path.
- Terminal state is never `SUCCESS` when any check failed or an exception occurred.
- Exported YAML re-imported via `/workflows/import` MUST reproduce an identical graph.
