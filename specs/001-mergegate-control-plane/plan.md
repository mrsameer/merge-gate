# Implementation Plan: MergeGate — Loop Engineering Control Plane

**Branch**: `001-mergegate-control-plane` | **Date**: 2026-07-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-mergegate-control-plane/spec.md`

## Summary

MergeGate is a visual control plane for autonomous coding: an engineer enters an objective, a
four-role loop (Success Criteria → Planning → Execution → Validation) proposes changes in an
isolated workspace, and a **deterministic, LLM-free acceptance engine** — never the execution
agent — computes the verdict. Failure becomes structured feedback for the next bounded attempt;
exhaustion rolls back clean; every run leaves a tamper-evident, replayable evidence bundle.

**Technical approach**: A React + React Flow single-page app renders the node-graph editor,
inspector, run console, and evidence screen, talking to a FastAPI control plane over REST + SSE.
A LangGraph orchestrator runs the durable, checkpointed loop with `interrupt()` human gates. Each
attempt executes in a disposable git worktree behind a provider-adapter interface (default: Cursor
CLI headless). The acceptance engine runs an ordered, LLM-free check pipeline and writes to an
append-only, hash-chained ledger (SQLite + JSONL) that exports as `evidence-bundle.json` and
replays with zero model calls.

## Technical Context

**Language/Version**: Backend Python 3.11+ (managed with `uv`); Frontend TypeScript 5.x on Node 20.

**Primary Dependencies**: Backend — FastAPI, `sse-starlette` (SSE), LangGraph + langgraph-checkpoint-sqlite, Pydantic v2, uvicorn, GitPython/subprocess git, PyYAML. Frontend — React 18, `@xyflow/react` (React Flow), Vite, Zustand (canvas/run state), native `EventSource` for SSE.

**Storage**: SQLite (run/attempt/ledger tables) + JSONL append-only event log, hash-chained; git worktrees on feature branches for per-attempt isolation. No external DB service.

**Testing**: Backend — `pytest` with `anyio` for async; Frontend — Vitest + React Testing Library, optional Playwright for one E2E happy-path. Demo target repo uses `pytest` (seconds-long suite).

**Target Platform**: Local/single-host — Linux or macOS server process + a modern desktop browser. Docker Compose optional (stretch).

**Project Type**: Web application (separate `frontend/` and `backend/`), plus a self-contained demo repo fixture.

**Performance Goals**: Demo-scale, single operator. SSE event-to-UI latency < 500 ms; acceptance pipeline for the demo task completes in < 60 s; replay of a completed verdict < 5 s with zero model calls.

**Constraints**: Acceptance engine MUST be LLM-free and deterministic (Principle I/II); identical recorded state ⇒ identical verdict; per-attempt isolation with clean rollback; bounded attempt/time/model-call budgets; anti-cheat protected paths + forbidden-diff patterns enforced pre-acceptance.

**Scale/Scope**: One operator, one target repo per run, a handful of workflow nodes, ≤ ~10 attempts per run. Not multi-tenant; no horizontal scaling, enterprise auth, or RAG in scope for v1.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | How this design satisfies it | Status |
|---|-----------|------------------------------|--------|
| I | Generation ≠ Acceptance | Execution runs in the harness adapter; the acceptance engine is a separate, LLM-free module invoked by the orchestrator. The agent can only emit a "claimed done" signal; it has no write path to the verdict. LLM-judge (if used) is an advisory field that the engine ignores for pass/fail. | PASS |
| II | Deterministic, Replayable Acceptance | Acceptance input = `commit SHA + validation config + tool versions + env fingerprint`, all recorded. A `replay` entrypoint re-runs the check pipeline from that state with the provider adapter disabled (zero model calls). Red-before/green-after enforced by running task tests on baseline worktree first. | PASS |
| III | Proof-Carrying Runs | Every event appended to a hash-chained ledger (`prev_hash`); `evidence-bundle.json` export includes contract, plan, diff, commands+exit codes, red→green, policy, retries, acceptance hash, cost, time, terminal state. | PASS |
| IV | Bounded Autonomy + Clean Rollback | Orchestrator enforces attempt/wall-clock/model-call budgets and a no-progress detector (failure-signature + unchanged-diff). Rollback = discard worktree, leave base repo green, emit honest report. Terminal-state enum is exhaustive; exceptions map to safe stops, never SUCCESS. | PASS |
| V | Failure→Feedback; Clarify Don't Guess | Validator emits structured failure objects consumed by the Planning node. A criteria-consistency check emits `CLARIFICATION_REQUIRED` on contradiction before execution. | PASS |
| — | Configurability & Integrity | Workflow is data (YAML/JSON) driving LangGraph assembly; provider behind an adapter interface; anti-cheat policy runs before the verdict. | PASS |

**Result**: PASS — no violations. Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/001-mergegate-control-plane/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (REST+SSE, workflow schema, evidence-bundle schema)
│   ├── control-plane-api.md
│   ├── workflow.schema.json
│   └── evidence-bundle.schema.json
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
backend/
├── src/
│   └── mergegate/
│       ├── api/                 # FastAPI routers: workflows, runs, control (pause/resume/stop), SSE stream
│       ├── orchestrator/        # LangGraph graph assembly from workflow config, checkpointer, human-gate interrupts
│       ├── acceptance/          # LLM-free engine: ordered checks (build, lint, tests, coverage, openapi, policy), verdict, replay
│       ├── harness/             # Provider adapter interface + Cursor CLI adapter (+ stubs for Aider/Claude/Codex)
│       ├── workspace/           # Git worktree lifecycle, command allowlist, timeouts, diff capture
│       ├── ledger/              # Append-only hash-chained store (SQLite + JSONL), evidence-bundle export
│       ├── criteria/            # Contract generation (hybrid), consistency/clarification detection
│       ├── models/              # Pydantic domain models (Run, Attempt, Contract, Verdict, LedgerEntry, ...)
│       └── config/              # Settings, budgets, provider/model selection (env + workflow-driven)
└── tests/
    ├── contract/                # API contract tests
    ├── integration/             # End-to-end loop, replay, rollback, clarification, policy-block
    └── unit/                    # Acceptance checks, hash chain, no-progress detector, failure signature

frontend/
├── src/
│   ├── canvas/                  # React Flow graph editor, node library, custom node types
│   ├── inspector/               # Selected-node settings panel
│   ├── console/                 # Collapsible run console + click-node-to-inspect
│   ├── evidence/                # Red→green, acceptance hash, replay button, bundle view
│   ├── state/                   # Zustand stores; SSE client
│   └── api/                     # REST client, types generated from contracts
└── tests/                       # Vitest component tests, optional Playwright happy-path

demo-repo/                       # Self-contained FastAPI order service fixture (created after official start)
├── app/
│   ├── orders/                  # POST /orders (target of the idempotency task)
│   └── auth/                    # Protected module (must NOT be modified)
└── tests/                       # Fast pytest suite; acceptance tests added by the loop

docker-compose.yml               # Optional (stretch): backend + frontend + demo-repo runner
```

**Structure Decision**: Web application layout — `backend/` (FastAPI control plane + LangGraph orchestrator + LLM-free acceptance engine + harness/workspace/ledger) and `frontend/` (React Flow control-plane UI), with a `demo-repo/` fixture that hosts the one real coding task. This split maps directly to the architecture in the spec and keeps the deterministic acceptance engine physically separate from the execution harness (Principle I).

## Complexity Tracking

> No Constitution Check violations — this section intentionally left empty.
