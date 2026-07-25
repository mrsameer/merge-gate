# MergeGate owner guide

This guide is for explaining, operating, and safely changing MergeGate. Read
the first three sections before a demo; use the failure table when a run stops.

## 1. The one-sentence product explanation

**MergeGate is a visual control plane for coding agents: an agent can propose
changes, but only deterministic acceptance checks and a human merge gate can
declare success.**

The key idea is the trust boundary:

```text
objective -> frozen acceptance contract -> agent edits an isolated worktree
          -> policy + tests + API checks -> evidence -> human merge decision
```

Never say “the agent completed the task” just because it emitted text or
edited files. Say “the proposal passed the frozen checks” only after the
`VALID PROOF` panel exists, and say “merged” only after a human approves the
final gate.

## 2. Mental model: four independent layers

| Layer | Job | Main code |
| --- | --- | --- |
| Browser | Lets an operator define, observe, and approve a run | `frontend/src/` |
| Control plane | Exposes REST/SSE endpoints and starts the bounded loop | `backend/src/mergegate/api/` |
| Generation | Runs a provider in a disposable worktree and captures its diff | `backend/src/mergegate/harness/`, `workspace/` |
| Acceptance | Runs deterministic checks, policy, red/green proof, and replay | `backend/src/mergegate/acceptance/` |

The generation layer **cannot** set a pass verdict. It returns only a diff,
changed files, transcript, and usage. The acceptance layer has no model client;
it consumes the frozen contract and command exit codes.

## 3. End-to-end run lifecycle

1. **Create run**: `POST /api/runs` creates a `Run` in `awaiting_gate`.
   No attempt has run yet.
2. **Generate criteria**: `POST /criteria:generate` creates a draft contract.
   For the demo repo, `api/runs.py::_CRITERION_PLAN` attaches real commands to
   named criteria.
3. **Save criteria**: `PUT /criteria` lets the operator edit commands before
   approval.
4. **Approve criteria**: `POST /criteria:approve` freezes the contract and
   records it in the hash-chained ledger.
5. **Start run**: `POST /runs/{id}:start` first checks for contradictory
   criteria, resets the demo target to a clean baseline, resolves a provider,
   and starts `drive_run` in a background thread.
6. **Baseline**: criteria run against the unchanged repository. Task-specific
   proof needs a red baseline before a later green result is meaningful.
7. **Execution**: the selected provider receives the objective plus any prior
   structured failure feedback and edits a new git worktree.
8. **Policy**: protected paths and forbidden added diff patterns are checked
   before validation.
9. **Validation**: deterministic commands run in the worktree. Their exit
   codes, stdout/stderr, duration, and red/green evidence feed a verdict hash.
10. **Decision**: a passing verdict becomes `awaiting_gate`; a failed verdict
    produces feedback and may retry. A human approval is the only path to
    `SUCCESS`.

## 4. Run states you must be able to explain

| State | Meaning | What the operator does |
| --- | --- | --- |
| `awaiting_gate` before start | Waiting for criteria approval | Generate, edit, save, approve criteria |
| `running` | An attempt is active | Watch SSE console; pause or stop if needed |
| `paused` | Cooperative pause between atomic operations | Resume or stop |
| `awaiting_gate` after pass | Deterministic proof passed; merge is still human-owned | Inspect proof, then approve or reject merge |
| `SUCCESS` | Human approved the merge gate | Inspect/export the evidence bundle |
| `CLARIFICATION_REQUIRED` | Frozen criteria contradict each other | Edit criteria, create a new run, and approve again |
| `POLICY_BLOCKED` | Proposal changed a protected file or introduced a banned diff pattern | Explain the rule, fix the agent/task, retry from a fresh run |
| `NO_PROGRESS` | Harness could not start, baseline proof was invalid, or repeated failure/diff was unchanged | Read the exact terminal reason, fix configuration/task, start a new run |
| `EXHAUSTED` | Attempt or model-call budget ended | Increase a justified budget or improve the objective/feedback |
| `TIMED_OUT` | Wall-clock budget or provider deadline ended | Increase time budget or fix a stuck provider/command |
| `HUMAN_REJECTED` | Reviewer rejected a passing proposal | Use the rejection reason for a new objective/run |
| `CANCELLED` | Operator stopped the run | Start a fresh run when ready |

Terminal states are final. The code deliberately has no terminal-to-success
transition.

## 5. What the UI controls call

| UI action | Frontend owner | Backend route/owner |
| --- | --- | --- |
| Create run | `inspector/InspectorPanel.tsx` | `api/runs.py::create_run` |
| Generate / save / approve criteria | `InspectorPanel.tsx` | `generate_criteria`, `edit_criteria`, `approve_criteria` |
| Start / pause / resume / stop | `InspectorPanel.tsx`, `layout/TopBar.tsx` | `start_run`, `pause_run`, `resume_run`, `stop_run` |
| Approve merge | `InspectorPanel.tsx` | `approve_gate` -> `gates.approve_merge` |
| Canvas editing | `canvas/`, Zustand `state/store.ts` | Workflow import/export API |
| Live console | `console/RunConsole.tsx` | `api/events.py` SSE stream |
| Ledger/evidence | `console/RunConsole.tsx`, `evidence/EvidencePanel.tsx` | `/ledger`, `/evidence`, `/replay` |
| Sign-in / credentials | `auth/AccountPanel.tsx` | `auth/router.py`, `auth/store.py` |

The UI does not decide whether a run passed. It only renders the API result
and incoming SSE events.

## 6. Failure diagnosis playbook

### `POLICY_BLOCKED`

Read the terminal `reason`. Typical examples:

- `forbidden diff pattern 'assert True' introduced in ...`: the agent added a
  fake or trivial assertion. Keep the test meaningful; do not remove the
  policy merely to pass.
- `protected path modified: ...`: the agent edited a protected path such as
  `app/auth/**`. Move the change to an allowed location or consciously change
  the policy before creating the run.

The implementation is `acceptance/policy.py`. It checks only changed paths
and **added** diff lines, which prevents deleting an old banned string from
being misclassified as a new violation.

### `NO_PROGRESS`

This is not success and not a generic error. Read the terminal reason:

- `harness could not run: Gemini CLI exited with 41 ...`: auth is missing or
  invalid in the environment supplied to Gemini. For user-owned runs, connect
  a Gemini key; for local Vertex, set ADC/project/location in `backend/.env`.
- `harness could not run: ... executable not found`: the CLI is not installed
  on the backend host or absent from `PATH`.
- `harness could not run: ... root/sudo ...`: Claude CLI was running as root.
  The Railway Docker image fixes this by starting Uvicorn as `mergegate`, not
  root.
- `baseline proof invalid`: the unchanged target already passes a check that
  is meant to prove the requested feature. Reset/fix the baseline, or choose
  a criterion that is genuinely red first.
- `no progress detected`: two consecutive attempts had the same deterministic
  failure signature and identical diff. Improve the objective/criteria or
  provider configuration; a third identical retry would waste money.

The no-progress detector lives in `orchestrator/no_progress.py` and compares
the failure signature plus captured diff, not the agent's self-report.

### `EXHAUSTED` or `TIMED_OUT`

- `EXHAUSTED`: `max_attempts` or `max_model_calls` has been reached. The
  default UI budget is 3 attempts, 30 minutes, and 120 model calls.
- `TIMED_OUT`: wall-clock budget hit zero/expired or a harness exceeded its
  own deadline. Gemini's adapter default is 600 seconds.

The guard is `orchestrator/budgets.py`. Changing budgets changes the cost and
safety envelope; explain why the increase is necessary before doing it.

### `CLARIFICATION_REQUIRED`

No model call should have happened. The approved contract contains opposing
requirements, so edit criteria and create a fresh approved run. The detector
is `criteria/consistency.py`.

### UI shows no live updates

1. Check browser Network for `GET /api/runs/{id}/events`.
2. Check `VITE_API_BASE_URL`; it must be the Railway backend URL ending in
   `/api`, not Vercel's own `/api` path.
3. Check Railway `CORS_ALLOW_ORIGINS` exactly matches the Vercel origin.
4. Check the run still exists. v1 keeps active runs and SSE history in
   process memory, so a backend restart returns an explicit 404 rather than
   pretending a run survived.

The frontend SSE base URL is `state/sseClient.ts`; it intentionally calls
`getApiBaseUrl()` from `api/client.ts`.

### GitHub sign-in errors

- `GitHub OAuth is not configured on this deployment`: set Railway
  `GITHUB_OAUTH_CLIENT_ID` and `GITHUB_OAUTH_CLIENT_SECRET`.
- Railway “train has not arrived”: generate/enable the Railway public domain
  and wait for deployment health.
- Vercel `404` after GitHub approval: the frontend must have the SPA callback
  rewrite in `frontend/vercel.json`; the GitHub callback itself points to
  Railway `/api/auth/github/callback`.
- Credential storage errors: set `MERGEGATE_CREDENTIAL_ENCRYPTION_KEY` and
  mount Railway storage at `/data`. Never put provider keys in Vercel env.

## 7. The safe way to change common features

### Add a new acceptance criterion

1. Add the model/type only if a new `CriterionType` or `CheckStep` is needed.
2. Add/adjust an evaluator in `acceptance/evaluators.py`.
3. Include the step in `acceptance/engine.py::PIPELINE_ORDER` only if it must
   participate in ordered, fail-fast validation.
4. Map the generated criterion to a real command in
   `api/runs.py::_CRITERION_PLAN` for the demo flow.
5. Add unit tests for evaluator behavior and an integration test proving the
   resulting verdict.

Do not make the agent decide that a new criterion passed.

### Add or change a provider

1. Implement `HarnessAdapter.propose_changes` in `harness/<provider>.py`.
2. Return only `HarnessResult(diff, changed_files, log, tokens, model_calls,
   usd)`; use `capture_diff(workspace)` instead of trusting model output.
3. Raise `HarnessError` for an invocation/auth problem and
   `HarnessTimeoutError` for a timeout.
4. Register the adapter in `harness/registry.py`.
5. Add the provider to the inspector select only after backend support exists.
6. Test prompt/feedback propagation, credential precedence, diff capture, and
   usage parsing with a fake adapter or command.

### Change the workflow canvas

1. Domain shape: `frontend/src/canvas/types.ts`.
2. Default graph: `canvas/defaultWorkflow.ts` and backend
   `orchestrator/default_workflow.py`.
3. UI editing behavior: `canvas/workflowEditing.ts` and `state/store.ts`.
4. Rendering: `canvas/GraphCanvas.tsx` / `RoleNode.tsx`.
5. Persistence/import/export: `canvas/workflowIO.ts` and
   `backend/api/workflows.py`.
6. Add matching frontend unit tests and backend serialization tests.

### Change a visible control or panel

Start in `frontend/src/layout/`, `inspector/`, `console/`, `evidence/`, or
`auth/`. Find its API client call in `frontend/src/api/client.ts`, then find
the route in `backend/src/mergegate/api/`. This is the fastest way to avoid a
frontend-only change that cannot persist or a backend route that no UI calls.

### Change data that must be secure

Secrets belong in `backend/src/mergegate/auth/store.py`; values are encrypted
with Fernet before SQLite storage and never returned by an API. The browser
sends them only to Railway over HTTPS. Do not add them to Zustand, localStorage,
Vercel environment variables, logs, evidence bundles, or a Git commit.

## 8. Tests and validation routine

Run the smallest relevant test first, then widen scope:

```bash
# Backend: a changed unit or integration behavior
cd backend
uv run pytest tests/unit/test_harness_gemini.py -q
uv run pytest tests/integration/test_happy_path.py -q
uv run pytest
uv run ruff check src tests
uv run pyright

# Frontend: a changed UI/API/SSE unit
cd frontend
npm test -- --run tests/unit/sse_client.test.ts
npm run build
npm run lint
```

For a full local demo, start FastAPI on `8000` and Vite on `5173`, then use the
scripted provider first. It proves the workflow without spending API money.

## 9. High-confidence judging answers

**Why is this safer than an autonomous coding agent?**
The agent is isolated in a disposable worktree and cannot set the verdict.
The acceptance engine runs frozen deterministic checks, policy checks, and
red/green proof; a human owns the final merge.

**What is “proof” here?**
The evidence records the contract, baseline command outputs, result command
outputs, exit codes, policy results, diff, hashes, and ledger. The same
verdict can be replayed with zero model calls.

**Why must the baseline fail?**
If the starting code already passes the task test, a passing result proves
nothing about the agent's change. Red baseline plus green result makes the
claim attributable to the proposed diff.

**What prevents endless retries?**
Attempt, wall-clock, and model-call budgets; repeated identical failures with
the same diff stop as `NO_PROGRESS`.

**What happens if the model is unavailable?**
The harness raises a truthful error and the run becomes `NO_PROGRESS` or
`TIMED_OUT`. It never becomes `SUCCESS` because a provider failed.

**Where are credentials stored?**
Only in backend storage encrypted with Fernet. The frontend never receives a
saved secret; Vercel does not store provider credentials.

## 10. Known limitations to answer honestly

- The active run registry and SSE buffer are in process memory. A backend
  restart cannot resume an in-progress v1 run; start a new run from a clean
  baseline.
- The default UI flow has a fixed budget. Making budgets operator-editable is
  a reasonable future enhancement.
- Live provider success depends on the CLI/runtime/auth being available on
  the backend host. Scripted demo runs are intentionally deterministic and
  credential-free.
- A passing result is merge-gated but does not automatically create a GitHub
  pull request. The human gate protects the decision; PR automation can be
  added as a separate explicit step.
