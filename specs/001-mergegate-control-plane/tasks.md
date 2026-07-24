---
description: "Task list for MergeGate — Loop Engineering Control Plane"
---

# Tasks: MergeGate — Loop Engineering Control Plane

**Input**: Design documents from `/specs/001-mergegate-control-plane/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: INCLUDED — the spec and constitution require TDD red-before/green-after and a reliability
suite, so contract/integration tests are first-class tasks (written to fail before implementation).

**Organization**: Tasks are grouped by user story (spec.md priorities) so each story is an
independently testable increment. Paths follow the web-app layout in plan.md
(`backend/src/mergegate/…`, `frontend/src/…`, `demo-repo/…`).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on incomplete tasks)
- **[Story]**: US1–US8, mapping to the spec's user stories

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and scaffolding

- [ ] T001 Create monorepo structure (`backend/`, `frontend/`, `demo-repo/`) per plan.md
- [ ] T002 [P] Initialize backend `uv` project with dependencies (fastapi, sse-starlette, langgraph, langgraph-checkpoint-sqlite, pydantic, uvicorn, pyyaml, GitPython) in `backend/pyproject.toml`
- [ ] T003 [P] Initialize frontend Vite + React 18 + TypeScript project with `@xyflow/react` and `zustand` in `frontend/package.json`
- [ ] T004 [P] Configure ruff + pyright (backend) and eslint + prettier (frontend)
- [ ] T005 [P] Scaffold `demo-repo/` FastAPI order service (`app/orders/`, protected `app/auth/`, fast `tests/` pytest suite) as the target task fixture

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure every user story depends on

**⚠️ CRITICAL**: No user-story work begins until this phase is complete

- [ ] T006 [P] Pydantic domain models (Run, Attempt, Contract, Criterion, Verdict, CheckResult, Policy, Budget, CostAccounting, StructuredFeedback) in `backend/src/mergegate/models/`
- [ ] T007 [P] Workflow/Node/Edge models with schema validation against `contracts/workflow.schema.json` in `backend/src/mergegate/models/workflow.py`
- [ ] T008 SQLite schema + connection/init (runs, attempts, ledger tables) in `backend/src/mergegate/ledger/store.py`
- [ ] T009 Append-only hash-chained ledger writer + JSONL mirror (`prev_hash` chaining) in `backend/src/mergegate/ledger/ledger.py` (depends on T008)
- [ ] T010 FastAPI app skeleton, router wiring, and error envelope in `backend/src/mergegate/api/main.py`
- [ ] T011 [P] SSE event stream endpoint + in-process event bus with `Last-Event-ID` reconnect in `backend/src/mergegate/api/events.py`
- [ ] T012 Workflow config loader (YAML/JSON) → LangGraph graph assembly in `backend/src/mergegate/orchestrator/graph.py` (depends on T007)
- [ ] T013 LangGraph SQLite checkpointer + run state machine + terminal-state enum + pause/resume/stop transitions in `backend/src/mergegate/orchestrator/runner.py` (depends on T012)
- [ ] T014 [P] Git worktree manager (create/discard, per-attempt branch, command allowlist, timeout, diff capture) in `backend/src/mergegate/workspace/worktree.py`
- [ ] T015 [P] Provider adapter interface `HarnessAdapter` in `backend/src/mergegate/harness/base.py`
- [ ] T016 Cursor CLI headless adapter implementing `HarnessAdapter` in `backend/src/mergegate/harness/cursor.py` (depends on T015)
- [ ] T017 [P] Settings/budgets/provider selection (env + workflow-driven) in `backend/src/mergegate/config/settings.py`
- [ ] T018 [P] React app shell + five-area layout scaffolding + REST client + SSE `EventSource` client in `frontend/src/state/` and `frontend/src/api/`
- [ ] T019 React Flow canvas base rendering the default four-role loop read-only in `frontend/src/canvas/` (depends on T018)

**Checkpoint**: Foundation ready — user stories can begin

---

## Phase 3: User Story 1 - Run an objective to a trustworthy verdict (Priority: P1) 🎯 MVP

**Goal**: Objective → hybrid contract → human approval → isolated execution → deterministic verdict → final gate → SUCCESS, with acceptance computed by a separate engine (not the agent).

**Independent Test**: Enter the idempotent-order objective, approve the contract, run once, and confirm the verdict comes from the acceptance engine (inputs are files/commands/exit-codes) via the happy-path integration test.

### Tests for User Story 1 ⚠️ (write first, ensure they FAIL)

- [ ] T020 [P] [US1] Contract test for `/runs`, `/criteria:generate|approve`, `/runs/{id}:start` in `backend/tests/contract/test_runs_api.py`
- [ ] T021 [P] [US1] Integration test happy-path loop (objective → contract → run → SUCCESS) in `backend/tests/integration/test_happy_path.py`

### Implementation for User Story 1

- [ ] T022 [P] [US1] Repo mapper + hybrid criteria generation grounded in real files in `backend/src/mergegate/criteria/generate.py`
- [ ] T023 [US1] Contract freeze + approval logic (`frozen_hash`) in `backend/src/mergegate/criteria/contract.py` (depends on T022)
- [ ] T024 [US1] Command runner capturing stdout/stderr/exit_code/duration in `backend/src/mergegate/acceptance/commands.py`
- [ ] T025 [US1] LLM-free acceptance engine driven by a pluggable criterion-evaluator registry, running the ordered pipeline build → lint → existing tests → new tests → migration apply/rollback → coverage → OpenAPI/API-compatibility in `backend/src/mergegate/acceptance/engine.py` (depends on T024)
- [X] T026 [US1] Verdict computation as a pure function over recorded state + `acceptance_hash` in `backend/src/mergegate/acceptance/verdict.py` (depends on T025)
- [X] T027 [US1] Wire four-role loop nodes (success_criteria, planning, execution→harness, validation→engine) in `backend/src/mergegate/orchestrator/nodes.py` (depends on T013, T016, T026)
- [X] T028 [US1] Runs API (create/get/start, criteria generate/edit/approve, gate) in `backend/src/mergegate/api/runs.py` (depends on T027)
- [X] T029 [US1] Final merge human gate → SUCCESS + branch/patch reference in `backend/src/mergegate/orchestrator/gates.py`
- [X] T030 [US1] Minimal UI wiring: Input node objective entry, criteria review/edit/approve, run, live node statuses + basic console in `frontend/src/inspector/` and `frontend/src/console/` (depends on T019, T028)
- [X] T073 [US1] Criterion-evaluator interface + registry with built-in evaluators for every FR-001c criterion type (build, tests, new-tests, required-file/feature-exists, protected-files, coverage-threshold, API-compatibility, performance-vs-baseline, architecture-conformance) in `backend/src/mergegate/acceptance/evaluators/` — demo exercises the concrete subset; perf-vs-baseline and architecture-conformance ship as evaluators wired through the same interface (depends on T025)
- [X] T074 [US1] Run-level cost accounting: aggregate and persist model calls, tokens, USD, and wall-clock from the harness adapter into the Run + ledger (FR-022) in `backend/src/mergegate/orchestrator/cost.py` (depends on T016, T027)

**Checkpoint**: US1 fully functional and demonstrable end-to-end (MVP)

---

## Phase 4: User Story 2 - Prove the green means something (Priority: P1)

**Goal**: Red-before/green-after proof + zero-model-call replay yielding the identical verdict.

**Independent Test**: Run a task whose attempt-1 stub fails for real; confirm baseline-FAILED / result-PASSED with hashes, then Replay reproduces the same `acceptance_hash` with zero model calls.

### Tests for User Story 2 ⚠️

- [X] T031 [P] [US2] Integration test red-before/green-after + replay-with-zero-model-calls in `backend/tests/integration/test_replay.py`

### Implementation for User Story 2

- [X] T032 [US2] Baseline red-check: run task tests on baseline worktree, assert ≥1 relevant test fails in `backend/src/mergegate/acceptance/baseline.py` (depends on T014, T025)
- [X] T033 [US2] Red→green evidence record + test/baseline/result hashes in `backend/src/mergegate/acceptance/evidence.py` (depends on T032)
- [X] T034 [US2] Replay entrypoint recomputing the verdict from `acceptance_input` with the provider adapter disabled in `backend/src/mergegate/acceptance/replay.py` (depends on T026)
- [X] T035 [US2] `/runs/{id}/replay` endpoint enforcing zero model calls in `backend/src/mergegate/api/runs.py` (depends on T034)
- [X] T036 [P] [US2] Evidence screen UI (baseline/result/verdict, hashes, Replay button) in `frontend/src/evidence/` (depends on T030)

**Checkpoint**: Validator-integrity story demonstrable independently

---

## Phase 5: User Story 3 - Failure changes the next attempt, within bounds (Priority: P1)

**Goal**: Structured failure feedback drives the next attempt; attempt/time/model-call budgets + no-progress detector bound autonomy; exhaustion rolls back clean with an honest report.

**Independent Test**: Force attempt-1 failure and confirm feedback reaches Planning and the counter advances; force repeated identical failures and confirm a safe stop with a discarded worktree.

### Tests for User Story 3 ⚠️

- [X] T037 [P] [US3] Integration test exhaustion → rollback and no-progress → safe stop in `backend/tests/integration/test_bounded.py`

### Implementation for User Story 3

- [X] T038 [US3] Structured failure feedback builder (criterion, command, exit_code, signature, location, attempt) in `backend/src/mergegate/acceptance/feedback.py` (depends on T026)
- [X] T039 [US3] Feedback → Planning wiring for the next attempt in `backend/src/mergegate/orchestrator/nodes.py` (depends on T027, T038)
- [X] T040 [US3] Budget enforcement (attempts, wall-clock, model calls) in `backend/src/mergegate/orchestrator/budgets.py` (depends on T013)
- [X] T041 [US3] `failure_signature` + no-progress detector (same signature + unchanged diff) in `backend/src/mergegate/orchestrator/no_progress.py` (depends on T038)
- [X] T042 [US3] Rollback: discard worktree, leave base repo green, emit undelivered report in `backend/src/mergegate/workspace/rollback.py` (depends on T014)
- [X] T043 [P] [US3] Attempt counter + retry reasons surfaced via SSE and console in `frontend/src/console/` (depends on T030)

**Checkpoint**: Bounded-autonomy story demonstrable independently

---

## Phase 6: User Story 4 - Clarify, don't guess (Priority: P2)

**Goal**: Contradictory/ambiguous criteria → structured clarification request, `CLARIFICATION_REQUIRED`, no execution.

**Independent Test**: Load the "return both 200 and 201" objective; confirm CLARIFICATION_REQUIRED with no code-change attempt.

### Tests for User Story 4 ⚠️

- [ ] T044 [P] [US4] Integration test contradictory criteria → CLARIFICATION_REQUIRED (no attempt) in `backend/tests/integration/test_clarification.py`

### Implementation for User Story 4

- [ ] T045 [US4] Criteria consistency/contradiction detector in `backend/src/mergegate/criteria/consistency.py` (depends on T023)
- [ ] T046 [US4] `CLARIFICATION_REQUIRED` terminal path + structured request payload in `backend/src/mergegate/orchestrator/runner.py` (depends on T045)
- [ ] T047 [P] [US4] Clarification-request UI panel in `frontend/src/console/` (depends on T030)

**Checkpoint**: Clarification story demonstrable independently

---

## Phase 7: User Story 5 - Anti-cheat policy enforcement (Priority: P2)

**Goal**: Protected paths unmodifiable; forbidden diff patterns rejected; `POLICY_BLOCKED` names the violation — enforced before any verdict.

**Independent Test**: Attempt an edit to `app/auth/**` or a `pytest.mark.skip` insertion; confirm POLICY_BLOCKED with the offending path/pattern.

### Tests for User Story 5 ⚠️

- [ ] T048 [P] [US5] Integration test protected-path + forbidden-diff → POLICY_BLOCKED in `backend/tests/integration/test_policy.py`

### Implementation for User Story 5

- [ ] T049 [US5] Protected-path + forbidden-diff policy checks in `backend/src/mergegate/acceptance/policy.py` (depends on T014)
- [ ] T050 [US5] Order policy before verdict in the pipeline + `POLICY_BLOCKED` wiring naming the offender in `backend/src/mergegate/acceptance/engine.py` and `orchestrator/runner.py` (depends on T049, T025)
- [ ] T051 [P] [US5] Policy config surfaced/edited in the node inspector UI in `frontend/src/inspector/` (depends on T030)

**Checkpoint**: Anti-cheat story demonstrable independently

---

## Phase 8: User Story 6 - Inspectable, exportable, tamper-evident receipts (Priority: P2)

**Goal**: Full hash-chained ledger timeline + `evidence-bundle.json` export with all required fields; tampering detectable.

**Independent Test**: Complete a run, export the bundle (all fields present), alter a prior ledger entry, and confirm hash-chain verification fails.

### Tests for User Story 6 ⚠️

- [ ] T052 [P] [US6] Integration test evidence-bundle field coverage + tamper detection in `backend/tests/integration/test_evidence_bundle.py`

### Implementation for User Story 6

- [ ] T053 [US6] Evidence-bundle assembler validating against `contracts/evidence-bundle.schema.json` in `backend/src/mergegate/ledger/bundle.py` (depends on T009)
- [ ] T054 [US6] Hash-chain verification utility in `backend/src/mergegate/ledger/verify.py` (depends on T009)
- [ ] T055 [US6] `/runs/{id}/ledger` + `/runs/{id}/evidence` endpoints in `backend/src/mergegate/api/runs.py` (depends on T053)
- [ ] T056 [P] [US6] Run-console timeline + click-node-to-inspect + evidence download UI in `frontend/src/console/` and `frontend/src/evidence/` (depends on T036, T043)

**Checkpoint**: Receipts/evidence story demonstrable independently

---

## Phase 9: User Story 7 - Author, configure, run, and inspect the loop visually (Priority: P3)

**Goal**: Rivet-style authoring — add nodes from a library, connect success/failure paths, edit only the selected node, top-bar controls, YAML/JSON export/import round-trip.

**Independent Test**: Build a loop by dragging + connecting nodes, edit one node in the inspector, run it, and export/re-import to reproduce the same graph.

### Tests for User Story 7 ⚠️

- [ ] T057 [P] [US7] Contract test for `/workflows` create/update/export/import round-trip in `backend/tests/contract/test_workflows_api.py`

### Implementation for User Story 7

- [ ] T058 [P] [US7] Node library + add/drag nodes + connect edges with success/failure paths in `frontend/src/canvas/` (depends on T019)
- [ ] T059 [P] [US7] Node inspector per-node-type settings editing in `frontend/src/inspector/` (depends on T030)
- [ ] T060 [US7] Workflows API (create/update/export/import YAML|JSON) in `backend/src/mergegate/api/workflows.py` (depends on T012)
- [ ] T061 [US7] Export/import round-trip serialization in `backend/src/mergegate/orchestrator/serialize.py` (depends on T007, T060)
- [ ] T062 [P] [US7] Top bar (name, save/export, run/pause/stop, status, attempt counter) + pause/resume/stop controls wired to `api/runs.py` in `frontend/src/` (depends on T030, T013)
- [ ] T063 [P] [US7] Export/import UI wiring and config round-trip verification in `frontend/src/canvas/` (depends on T060)

**Checkpoint**: Visual authoring story demonstrable independently

---

## Phase 10: User Story 8 - Provider is configurable, not hardcoded (Priority: P3)

**Goal**: Provider/model family selected via config per Agent node; a compatible provider can be swapped without changing the workflow.

**Independent Test**: Switch the configured provider and confirm execution uses it with no change to the workflow definition.

### Tests for User Story 8 ⚠️

- [ ] T064 [P] [US8] Adapter/integration test: provider selected via config; swap without workflow change in `backend/tests/integration/test_provider_swap.py`

### Implementation for User Story 8

- [ ] T065 [US8] Provider selection per Agent node + config plumbing in `backend/src/mergegate/config/providers.py` (depends on T017, T027)
- [ ] T066 [P] [US8] Stub adapters (Aider / Claude Agent SDK / Codex) implementing `HarnessAdapter` in `backend/src/mergegate/harness/` (depends on T015)

**Checkpoint**: Provider-swap story demonstrable (single wired adapter + swap story)

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Reliability, packaging, and demo readiness

- [ ] T067 [US-all] Reliability suite — all ten scenarios in `backend/tests/integration/test_reliability.py` (2-attempt success; invalid command; timeout; human rejection; manual stop; protected-file blocked; exhausted; contradiction→clarification; mid-run refresh; backend restart)
- [ ] T068 [P] Saved demo fixtures — contradictory-task workflow + default four-role workflow in `demo-repo/fixtures/`
- [ ] T069 [P] Docker Compose (backend + frontend + demo-repo runner) in `docker-compose.yml` (stretch)
- [ ] T070 [P] README, architecture diagram, and 6-minute demo script in `docs/`
- [ ] T071 Run `quickstart.md` scenarios A–F end-to-end and fix gaps
- [ ] T072 [P] Frontend component tests (canvas, inspector, console, evidence) in `frontend/tests/`

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (P1)**: no dependencies
- **Foundational (P2)**: depends on Setup — BLOCKS all user stories
- **User Stories (P3–P10)**: depend on Foundational; then orderable by priority
  - US2, US3 build on US1's acceptance engine/loop; US6 builds on the ledger + US2/US3 UI
  - US4, US5, US7, US8 are largely independent once Foundational is done
- **Polish (P11)**: depends on the targeted stories being complete

### MVP scope

**User Story 1 only** (Setup → Foundational → Phase 3) is the minimum demonstrable product: a real
loop with a deterministic verdict. US2 (integrity/replay) and US3 (bounded autonomy) are the next two
P1 increments that complete the graded core.

### Within each story

- Tests written first and failing → models → services → endpoints → UI wiring
- Commit after each task or logical group; never leave `main` broken

### Parallel opportunities

- Setup: T002, T003, T004, T005 in parallel
- Foundational: T006, T007, T011, T014, T015, T017, T018 in parallel (T008→T009, T012→T013, T015→T016 are sequential)
- Once Foundational is done, P1 stories US1→US2→US3 proceed in order; P2/P3 stories can be split across contributors
- Within a story, [P] tasks touch different files and can run together

---

## Parallel Example: User Story 1

```bash
# Tests first (fail before implementation):
Task: "Contract test for /runs APIs in backend/tests/contract/test_runs_api.py"      # T020
Task: "Integration test happy-path loop in backend/tests/integration/test_happy_path.py"  # T021

# Then parallel implementation where files don't overlap:
Task: "Hybrid criteria generation in backend/src/mergegate/criteria/generate.py"     # T022
Task: "Command runner in backend/src/mergegate/acceptance/commands.py"               # T024
```

---

## Notes

- [P] = different files, no incomplete dependencies. [Story] maps each task to a spec user story.
- The acceptance engine (T024–T026, T032–T034, T049–T050) MUST remain LLM-free and separate from the
  harness (Constitution Principle I). Replay (T034–T035) MUST make zero model calls (Principle II).
- Verify red-before/green-after (US2) on a genuine failure — never fake the first red.
- Total: 74 tasks across 11 phases. (T073–T074 were appended to Phase 3/US1 during `/speckit-analyze` remediation — closing FR-001c criterion-type coverage and FR-022 cost accounting — so their IDs sort after the polish phase but they execute within US1 per their dependencies.)
