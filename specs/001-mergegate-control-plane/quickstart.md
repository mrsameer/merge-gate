# Quickstart & Validation Guide: MergeGate

**Feature**: 001-mergegate-control-plane | **Date**: 2026-07-24

This guide proves the feature works end-to-end. It references [contracts/](contracts/) and
[data-model.md](data-model.md) rather than duplicating them. Implementation code lives in
`tasks.md` (Phase 2) and the source tree, not here.

## Prerequisites

- Python 3.11+ with `uv` installed (backend).
- Node 20+ (frontend).
- `git` on PATH (worktree isolation).
- The credential-free `Scripted demo` provider for deterministic scenarios A–F. External
  providers remain selectable per run; they are not required for the reproducible path (FR-034).

## Setup

```bash
# Backend
cd backend
uv sync --frozen
uv run uvicorn mergegate.api.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm ci
npm run dev   # serves the control plane UI, proxying /api to :8000
```

The `demo-repo/` FastAPI order service is the target repository for the validation scenarios below.
Save the default workflow before creating a run. For a live Vertex AI variant, authenticate with
ADC, set `GOOGLE_GENAI_USE_VERTEXAI=true`, `GOOGLE_CLOUD_LOCATION=asia-south1`, and
`GOOGLE_CLOUD_PROJECT`, then choose Gemini CLI / `gemini-2.5-flash` in the Input inspector.
Never set or commit an API key for that ADC-backed validation.

## Scenario A — Happy path: objective → contract → run → success (US1, US2, US3)

1. Open the UI. Confirm the five areas render: top bar, node-library panel, canvas, inspector,
   run console (FR-026b).
2. Add/confirm the default four-role loop on the canvas (Input → Success Criteria → Human Gate →
   Planning → Execution → Validator → Decision → Success/Stop). Connect nodes if authoring from
   scratch (FR-026a).
3. In the Input node, enter the objective: *"Add idempotent order creation to `POST /orders`.
   Require an `Idempotency-Key` header. Same key + same body → original order, no new row. Same key
   + different body → HTTP 409. Add tests + OpenAPI docs. Do not modify the auth module."*
4. Trigger criteria generation (hybrid). **Expect** the six repository-grounded criteria:
   `feature-exists`, `existing-tests`, `new-tests`, `idempotency-key-required`,
   `idempotent-order-reuse`, and `idempotency-key-conflict` (FR-001c).
5. Make an equivalent command edit (for example change one pytest `-q` flag to `-qq`), save it,
   then approve the contract at the Human Gate. **Expect** the contract to freeze (FR-003).
6. Start the run. **Expect** attempt 1 to create an isolated git worktree and apply the scripted
   idempotency change. The acceptance engine separately runs the unchanged baseline and the
   proposed result: task-specific checks fail for real on the baseline and pass on the result.
   The baseline red is proof of a missing feature, not a fabricated failed execution attempt.
7. **Expect** the run to stop at the final merge gate with `VALID PROOF`, not at `SUCCESS`.
8. Approve the final merge gate. **Expect** terminal state `SUCCESS` and a branch/patch reference.

**Pass criteria**: SC-001, SC-002, SC-003, SC-004, SC-010 demonstrated; verdict produced by the
acceptance engine, not the agent.

## Scenario B — Validator integrity & replay (US2)

1. On the completed run, open the Evidence screen. **Expect**: `Baseline: FAILED as expected`,
   `Result: PASSED`, `Verdict: VALID PROOF`, plus test/baseline/result hashes.
2. Click **Replay Validation**. **Expect** an identical verdict (same `acceptance_hash`) with **zero
   model calls** recorded in cost accounting (FR-010, SC-001).

## Scenario C — Anti-cheat policy (US5)

1. Run the policy integration variant where the attempted diff edits `app/auth/**` or inserts
   `pytest.mark.skip` (the deterministic fixture is
   `backend/tests/integration/test_policy.py`).
2. **Expect** terminal state `POLICY_BLOCKED` with the offending path/pattern named (FR-017/FR-018,
   SC-007). No verdict is granted.

## Scenario D — Clarify, don't guess (US4)

1. Load the saved contradictory objective: *"return both 200 and 201 for the same successful
   request."*
2. Start the run. **Expect** `CLARIFICATION_REQUIRED` with a structured clarification request and
   **no** code-change attempt (FR-016, SC-006).

## Scenario E — Bounded autonomy & clean rollback (US3)

1. In a second scripted UI run, replace `feature-exists` with
   `python -c "import sys; sys.exit(1)"`, then save, approve, and start.
2. **Expect** the run to stop as `NO_PROGRESS` (or `EXHAUSTED` on budget), the worktree discarded,
   the base repo left green, and an honest undelivered report (FR-013/FR-014/FR-015, SC-005).

## Scenario F — Config round-trip & inspection (US6, US7)

1. Export the workflow as YAML (`/workflows/{id}/export?format=yaml`), then import it back.
   **Expect** an identical graph that reruns the same loop (FR-028a, SC-014).
2. Click any completed/failed node in the run console. **Expect** its agent input/output, commands
   and tools used, files changed, validation results, retry reason, and status (FR-032/FR-033).
3. Export `evidence-bundle.json`. Alter any prior ledger entry and re-verify. **Expect** the hash
   chain to fail verification at the changed sequence (FR-019, SC-008). The executable tamper
   check is `backend/tests/integration/test_evidence_bundle.py`.

## Reliability suite (SC-011)

Run all ten scenarios before feature freeze: (1) 2-attempt success; (2) invalid command; (3) agent
timeout; (4) human rejection; (5) manual stop; (6) protected-file edit blocked; (7) exhausted
attempts; (8) contradictory criteria → clarification; (9) mid-run browser refresh (SSE reconnect via
`Last-Event-ID`); (10) backend restart → resume from checkpoint or documented limitation.

## Automated validation entry points

- Backend contract tests: `cd backend && uv run pytest tests/contract`
- Backend integration (loop/replay/rollback/clarification/policy): `uv run pytest tests/integration`
- Frontend component tests: `cd frontend && npm test`
- Containerized UI: `docker compose up --build --wait` (the backend image includes the locked
  demo acceptance test runner)
