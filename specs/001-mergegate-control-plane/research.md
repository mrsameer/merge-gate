# Phase 0 Research: MergeGate

**Feature**: 001-mergegate-control-plane | **Date**: 2026-07-24

All Technical Context items were resolved from the locked decisions in the spec's Assumptions
section — there are **no open `NEEDS CLARIFICATION` markers**. This document records each decision,
its rationale, and the alternatives considered, so the choices are defensible.

## R1. Orchestration engine

- **Decision**: LangGraph with the SQLite checkpointer and `interrupt()` for human gates.
- **Rationale**: Gives durable, checkpointed graph execution and first-class human-in-the-loop
  pauses for free — directly supports pause/resume/stop and mid-run recovery (Principle IV,
  FR-023). The graph is assembled at runtime from the workflow config, so paths are data, not code.
- **Alternatives considered**: Hand-rolled state machine (more control but re-implements durability
  and interrupts); Temporal/Celery (heavy, external services, over-scoped for a single-operator demo);
  Prefect/Airflow (data-pipeline oriented, poor fit for interactive human gates).

## R2. Deterministic acceptance (the differentiator)

- **Decision**: A standalone, LLM-free `acceptance/` module invoked by the orchestrator, running an
  ordered pipeline: build → lint/typecheck → existing suite → new acceptance tests → migration
  up/down → coverage → API/schema contract → protected-path & forbidden-diff policy. Each step
  captures stdout/stderr, exit code, and duration. Verdict is a pure function of recorded state.
- **Rationale**: Physical and process separation from the harness is the product thesis
  (Principle I). A pure function over `(commit SHA, validation config, tool versions, env
  fingerprint)` guarantees identical-state ⇒ identical-verdict and enables zero-model replay
  (Principle II).
- **Alternatives considered**: Letting the execution agent self-report (explicitly disqualified);
  a single "run tests" step (misses regressions, coverage, schema, and anti-cheat signals);
  an LLM judge as arbiter (violates Principle I — allowed only as advisory rubric input).

## R3. Red-before / green-after protocol

- **Decision**: For each task-specific acceptance test, run it on the **baseline** worktree and
  assert ≥1 relevant test fails; run the agent; run the exact same tests on the changed worktree and
  accept only on pass. Record test hash, baseline-result hash, result hash.
- **Rationale**: Proves the green means something and blocks "delete the test to pass" (Principle II,
  FR-009). The first failure is genuine (TDD stub), never faked.
- **Alternatives considered**: Only checking post-change pass (a vacuous or agent-weakened test would
  pass trivially); trusting coverage alone (gameable without the baseline-fail assertion).

## R4. Per-attempt isolation & rollback

- **Decision**: One `git worktree` on a fresh feature branch per attempt, with a command allowlist,
  per-command timeout, and diff-size policy. Rollback = remove the worktree; the base repo is never
  mutated in place.
- **Rationale**: Disposable isolation gives clean rollback and prevents a failed attempt from
  polluting the base repo (Principle IV, FR-011/FR-015). Worktrees are cheap vs. full clones/containers.
- **Alternatives considered**: In-place edits + `git reset` (risk of partial/dirty state); full clone
  per attempt (slower, more disk); Docker container per attempt (stronger isolation but heavier —
  deferred to a stretch bonus, not required for the core).

## R5. Provider adapter (no hardcoding)

- **Decision**: A narrow `HarnessAdapter` interface (`propose_changes(objective, feedback, workspace)`
  → diff + logs + token/cost) with a default **Cursor CLI headless** adapter and stub adapters for
  Claude Agent SDK / Aider / Codex. Provider and model family are selected via config/env, surfaced
  per Agent node in the workflow.
- **Rationale**: One interface proves "provider not hardcoded" (FR-034/FR-035) with a single wired
  adapter and a one-line swap story; a live second-provider swap is a bonus.
- **Alternatives considered**: Calling a model API directly (not a real coding harness — fails the
  "real filesystem+shell+test execution" requirement); hardcoding Cursor (fails no-hardcoding).

## R6. Tamper-evident receipts / evidence bundle

- **Decision**: Append-only ledger where each entry stores `prev_hash = H(prev_entry)`; mirrored as
  SQLite rows (query/timeline) and a JSONL file (portable). `evidence-bundle.json` is assembled from
  the ledger at run completion.
- **Rationale**: Hash chaining makes any retroactive edit detectable (Principle III, FR-019/FR-020).
  JSONL keeps the bundle portable and diff-friendly; SQLite powers the run-console timeline.
- **Alternatives considered**: Plain log file (not tamper-evident); full Merkle tree (overkill for a
  linear event stream); external audit service (out of scope).

## R7. No-progress detector

- **Decision**: `failure_signature = H(sorted(failed_criterion_ids) + normalized_error_messages)`.
  Stop as `NO_PROGRESS` when the same signature repeats across consecutive attempts **and** the git
  diff has not materially changed.
- **Rationale**: Prevents infinite/undead loops with a real signal, not just a counter (Principle IV,
  FR-014). Requiring unchanged-diff avoids false stops when the agent is genuinely iterating.
- **Alternatives considered**: Attempt-count-only cap (misses stuck-but-not-exhausted loops);
  error-string equality (brittle to line numbers/timestamps — hence normalization).

## R8. Contract generation & clarification

- **Decision**: Hybrid by default — the Success Criteria role proposes measurable criteria from the
  objective + repo map; the engineer edits/prioritizes/approves. A pre-execution consistency check
  detects contradictory criteria and emits `CLARIFICATION_REQUIRED`.
- **Rationale**: Matches the required three modes with hybrid default (FR-001a) and clarify-don't-guess
  (Principle V, FR-016). Grounding in the repo map keeps criteria tied to real files (FR-001).
- **Alternatives considered**: Free-text-only criteria (not machine-checkable); agent-only with no
  human approval (violates contract-before-code).

## R9. Frontend graph editor

- **Decision**: React 18 + `@xyflow/react` (React Flow) with custom node types for the 8 node kinds,
  Zustand for canvas/run state, native `EventSource` for SSE.
- **Rationale**: React Flow provides drag/zoom/connect/custom-nodes out of the box, satisfying the
  Rivet-style authoring experience (FR-026/FR-026a/FR-026b) without building a graph editor from
  scratch.
- **Alternatives considered**: Rivet itself (a product, not an embeddable lib for our control plane);
  raw SVG/canvas (reinvents pan/zoom/edges); a form wizard (explicitly disqualified — "not a wizard").

## R10. Transport: REST + SSE

- **Decision**: REST for CRUD/control actions; Server-Sent Events for the live run event stream.
- **Rationale**: SSE is a natural fit for a one-way server→client event timeline and reconnects
  cleanly on browser refresh (edge case in spec). Simpler than WebSockets for this unidirectional need.
- **Alternatives considered**: WebSockets (bidirectional complexity we don't need); polling (laggy,
  wasteful); gRPC streaming (browser friction).

## R11. Demo task & repo

- **Decision**: A compact FastAPI order service; task = idempotent `POST /orders` with an
  `Idempotency-Key` header (same key+body → original order/no new row; same key+different body → 409),
  plus tests + OpenAPI docs; `app/auth/**` is protected. Repo created only after the official start.
- **Rationale**: Requires planning across files, real implementation, validation, and iteration, yet
  the pytest suite runs in seconds — demonstrable within 5–7 minutes (FR/SC coverage, SC-010).
- **Alternatives considered**: Twenty CRM real task (high setup variance — kept as a stretch, §7 of the
  build doc); a trivial one-file task (too weak to prove planning+iteration).

## Open risks (tracked, not blocking)

- Cursor CLI headless auth/credits must be validated before the demo (assumption in spec).
- Backend restart mid-run: rely on LangGraph checkpointer for resume, else document the limitation
  (spec edge case + SC-011 scenario 10).
- Keep the acceptance pipeline fast; long-running checks threaten the 5–7 minute demo budget.
