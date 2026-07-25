# MergeGate

MergeGate is a visual control plane for autonomous coding. Coding providers
propose changes inside disposable git worktrees; a separate, deterministic,
LLM-free acceptance engine decides whether those changes advance. Every run is
bounded, ends in an explicit state, and records inspectable evidence.

The bundled FastAPI order service and scripted provider make the complete flow
reproducible without credentials or network access. A Gemini CLI adapter is
also available for a real coding-agent run.

## What it demonstrates

- **Contract before code:** success criteria remain editable until explicit
  approval, then freeze for the run.
- **Generation is not acceptance:** the harness can edit files but cannot set
  the verdict. Commands, exit codes, policy checks, and recorded state determine
  acceptance.
- **Genuine proof:** task tests must be red on the unchanged baseline and green
  on the proposed result. Replay reproduces the verdict with zero model calls.
- **Bounded autonomy:** failed checks become structured feedback for the next
  attempt; attempt, time, and model-call budgets prevent unbounded retries.
- **Inspectable receipts:** a hash-chained ledger feeds the live console and
  terminal evidence bundle.
- **Clarify, do not guess:** a contradictory contract stops before execution
  instead of being reported as progress.

See the [architecture and trust boundaries](docs/architecture.md) and the
[timed six-minute demo](docs/demo-script.md).

## Track B recorded demonstrations

These are captioned, silent browser walkthroughs. Videos 1 and 2 use an
isolated local scripted run so the controls and outcomes are reproducible;
video 3 uses a real three-attempt Claude Code run against the bundled
`demo-repo`. Use the [six-minute narration script](docs/demo-script.md) to
present the complete five-to-seven-minute walkthrough. The links below open
the browser-playable MPEG-4 assets published on the
[Track B demonstration videos release](https://github.com/mrsameer/merge-gate/releases/tag/track-b-demo-videos-2026-07-25).

1. **Coding objective entered** — [play `01-objective-criteria-workflow.m4v`](https://github.com/mrsameer/merge-gate/releases/download/track-b-demo-videos-2026-07-25/01-objective-criteria-workflow.m4v)
   shows selecting the Input node and entering the objective, repository, and provider.
2. **Success criteria generated or edited** — [play `01-objective-criteria-workflow.m4v`](https://github.com/mrsameer/merge-gate/releases/download/track-b-demo-videos-2026-07-25/01-objective-criteria-workflow.m4v)
   shows generated criteria, review, save, and explicit contract approval.
3. **Four-agent loop configured** — [play `01-objective-criteria-workflow.m4v`](https://github.com/mrsameer/merge-gate/releases/download/track-b-demo-videos-2026-07-25/01-objective-criteria-workflow.m4v)
   shows Success Criteria, Planning, Execution, and Validator in the canvas.
4. **Workflow saved or exported** — [play `01-objective-criteria-workflow.m4v`](https://github.com/mrsameer/merge-gate/releases/download/track-b-demo-videos-2026-07-25/01-objective-criteria-workflow.m4v)
   shows the save and YAML export actions before the run is created.
5. **Execution against a repository** — [play `01-objective-criteria-workflow.m4v`](https://github.com/mrsameer/merge-gate/releases/download/track-b-demo-videos-2026-07-25/01-objective-criteria-workflow.m4v)
   shows the isolated run executing its approved acceptance contract against `demo-repo`.
6. **Real validation evidence** — [play `01-objective-criteria-workflow.m4v`](https://github.com/mrsameer/merge-gate/releases/download/track-b-demo-videos-2026-07-25/01-objective-criteria-workflow.m4v)
   shows `VALID PROOF`, the baseline/result verdict, acceptance hashes, and verdict replay.
7. **Failure feeds another iteration** — [play `02-retry-evidence-inspection.m4v`](https://github.com/mrsameer/merge-gate/releases/download/track-b-demo-videos-2026-07-25/02-retry-evidence-inspection.m4v)
   shows the failed criterion, exact structured feedback, and the next attempt.
8. **Later success or safe stop** — [play `02-retry-evidence-inspection.m4v`](https://github.com/mrsameer/merge-gate/releases/download/track-b-demo-videos-2026-07-25/02-retry-evidence-inspection.m4v)
   shows the repeated failure becoming the explicit, safe `NO_PROGRESS` terminal state.
9. **Inspectable sessions and changes** — [play `03-bonus-cost-streaming-isolation-provider.m4v`](https://github.com/mrsameer/merge-gate/releases/download/track-b-demo-videos-2026-07-25/03-bonus-cost-streaming-isolation-provider.m4v)
   shows streamed agent work, commands, worktree paths, diff metadata, and ledger receipts.

### Bonus capabilities

- **Token, model-call, and USD tracking** — [play `03-bonus-cost-streaming-isolation-provider.m4v`](https://github.com/mrsameer/merge-gate/releases/download/track-b-demo-videos-2026-07-25/03-bonus-cost-streaming-isolation-provider.m4v)
  shows the harness receipt's token, call, and USD values.
- **Live agent and command streaming** — [play `03-bonus-cost-streaming-isolation-provider.m4v`](https://github.com/mrsameer/merge-gate/releases/download/track-b-demo-videos-2026-07-25/03-bonus-cost-streaming-isolation-provider.m4v)
  shows the Claude Code transcript and command events from the real run.
- **Isolated git worktrees** — [play `03-bonus-cost-streaming-isolation-provider.m4v`](https://github.com/mrsameer/merge-gate/releases/download/track-b-demo-videos-2026-07-25/03-bonus-cost-streaming-isolation-provider.m4v)
  shows the disposable worktree path, changed files, and diff recorded for the attempt.
- **Pause, resume, and checkpoint recovery** — the top-bar controls and SSE-backed run console are covered in the
  [demo script](docs/demo-script.md#before-the-clock) and [run-state guide](#run-states).
- **Reusable versioned templates** — the default and contradictory YAML fixtures are documented in
  [`demo-repo/fixtures/`](demo-repo/fixtures/).
- **External coding-harness integration** — [play `03-bonus-cost-streaming-isolation-provider.m4v`](https://github.com/mrsameer/merge-gate/releases/download/track-b-demo-videos-2026-07-25/03-bonus-cost-streaming-isolation-provider.m4v)
  records the external Claude Code provider and Sonnet model on a real attempt.

## Repository map

| Path | Purpose |
| --- | --- |
| [`frontend/`](frontend/) | React, React Flow, Zustand, REST/SSE control-plane UI |
| [`backend/`](backend/) | FastAPI API, orchestration, provider adapters, acceptance, ledger |
| [`demo-repo/`](demo-repo/) | Small FastAPI order service targeted by demo runs |
| [`demo-repo/fixtures/`](demo-repo/fixtures/) | Importable default and contradictory workflows |
| [`specs/001-mergegate-control-plane/`](specs/001-mergegate-control-plane/) | Spec Kit requirements, plan, contracts, and validation guide |

## Local setup

Prerequisites:

- Python 3.11 or newer
- [`uv`](https://docs.astral.sh/uv/)
- Node.js 20 or newer and npm
- Git
- A modern browser

From a clean clone, start the backend:

```bash
cd backend
uv sync --frozen
uv run uvicorn mergegate.api.main:app --reload --port 8000
```

In a second terminal, start the frontend:

```bash
cd frontend
npm ci
npm run dev
```

Check the API, then open <http://localhost:5173>:

```bash
curl --fail http://localhost:8000/api/health
```

The Input inspector defaults the repository to `demo-repo` and the provider to
`Scripted demo`. Import
[`default-four-role-workflow.yaml`](demo-repo/fixtures/default-four-role-workflow.yaml),
select the Input node, enter an objective, and create the run. The scripted
provider applies deterministic demo changes and makes no model calls.

## Docker setup

Docker Compose starts the control plane plus a separately health-checked
demo-repository service:

```bash
docker compose up --build --wait
docker compose ps
curl --fail http://localhost:8000/api/health
curl --fail http://localhost:9000/openapi.json
```

Open <http://localhost:5173>. Stop and remove the containers when finished:

```bash
docker compose down
```

The shipped backend image does not install development test tools or
third-party provider CLIs. Compose therefore validates service health, the
browser control plane, workflow persistence, criteria generation, and truthful
retry/safe-stop behavior out of the box. Use the local setup for the complete
passing Track B proof or Gemini CLI. Extending the backend image with the target
repository's test tools is required before claiming a passing containerized
acceptance run; never describe a missing tool as success.

## Vertex AI Gemini 2.5 Flash in Mumbai

The Gemini adapter runs the installed `gemini` CLI headlessly inside each
attempt worktree. For Vertex AI, authenticate with Application Default
Credentials (ADC); no API key belongs in this repository.

The backend automatically loads `backend/.env` at startup. Copy
[`backend/.env.example`](backend/.env.example) to `backend/.env`, then place
your local provider configuration there. `.env` is ignored by Git and real
shell environment variables take precedence.

Run the interactive login only when ADC is not already configured:

```bash
gcloud auth application-default login
```

Set the Vertex routing configuration in `backend/.env`:

```bash
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT="your-google-cloud-project"
GOOGLE_CLOUD_LOCATION=asia-south1
```

Verify ADC once with `gcloud auth application-default print-access-token
>/dev/null`, then start the backend normally. In the Input inspector choose `Gemini CLI`, set
the model to `gemini-2.5-flash`, and only then create the run. The provider and
model are frozen onto that run. The acceptance engine remains LLM-free: a
Gemini failure is surfaced as failure or a safe stop and is never converted to
success.

Never commit credentials, ADC files, access tokens, CLI home directories, or
generated local settings. `GOOGLE_CLOUD_PROJECT` is
configuration, not a credential; use a project where Vertex AI access and
billing are already authorized.

## Running a workflow

1. Import a fixture or edit the graph with the node library and inspector.
2. Save or export the workflow as YAML/JSON.
3. Select Input, enter the objective and repository, then choose the provider.
4. Create the run, generate criteria, edit or reprioritize them, and save.
5. Approve the criteria. Approval freezes the contract.
6. Start the run and watch node status, attempts, retries, and ledger events.
7. Inspect validation evidence. Approve the final merge gate only after a
   passing deterministic verdict.
8. Download terminal evidence or replay a completed verdict. Replay adds zero
   model calls and must preserve the `acceptance_hash`.

The contradictory fixture is
[`contradictory-task-workflow.yaml`](demo-repo/fixtures/contradictory-task-workflow.yaml).
Use its objective exactly as saved:

> POST /orders must return both 200 and 201 for the same successful request.

The expected result is `CLARIFICATION_REQUIRED`, attempt 0, skipped execution
and validation, and the message “No execution attempt was created.”

## Run states

Non-terminal states are `awaiting_gate`, `running`, and `paused`. Every other
outcome is terminal:

| Terminal state | Meaning |
| --- | --- |
| `SUCCESS` | Deterministic checks passed and the operator approved the final gate. |
| `CLARIFICATION_REQUIRED` | Criteria conflict or need clarification; execution did not proceed. |
| `HUMAN_REJECTED` | The operator rejected the final merge gate. |
| `EXHAUSTED` | The attempt or model-call budget ended without delivery. |
| `NO_PROGRESS` | Consecutive failures had the same signature and no material diff progress. |
| `TIMED_OUT` | The wall-clock budget expired. |
| `POLICY_BLOCKED` | A protected path or forbidden diff pattern was detected. |
| `CANCELLED` | The operator stopped the run. |

An exception, provider failure, timeout, unavailable evidence bundle, or failed
command is never a synonym for `SUCCESS`.

## Quality gates

Run the same local gates used to validate the repository:

```bash
cd backend
uv sync --frozen
uv run pytest -q
uv run ruff format --check .
uv run ruff check .
uv run pyright

cd ../frontend
npm ci
npm test
npm run lint
npm run format:check
npm run build
```

The API scenarios are described in the
[quickstart and validation guide](specs/001-mergegate-control-plane/quickstart.md);
the wire contracts live in
[`control-plane-api.md`](specs/001-mergegate-control-plane/contracts/control-plane-api.md).

## Known limitations

- The API's workflow/run registry and SSE replay buffer are process-local.
  Ledgers are written to temporary SQLite/JSONL files, but the application does
  not reload run records after a backend restart. A browser refresh while the
  same backend process is alive reconnects from `Last-Event-ID`; a backend
  restart cannot resume the run through the public API and must be reported as
  a limitation, never silently reconstructed.
- This is a local, single-operator system. Authentication, multi-tenancy,
  horizontal scaling, and concurrent-run scheduling are outside v1.
- Pause is cooperative: it takes effect after the active node yields.
- Provider CLIs, credentials, quota, network access, and model behavior are
  external dependencies. The scripted provider is the reproducible offline
  path; success with it does not prove that an external provider is available.
- The default UI repository value targets this monorepo's `demo-repo`.
  Arbitrary repositories must be local git repositories visible to the backend.

## Further reading

- [Architecture](docs/architecture.md)
- [Six-minute Track B demo script](docs/demo-script.md)
- [Feature specification](specs/001-mergegate-control-plane/spec.md)
- [Evidence bundle schema](specs/001-mergegate-control-plane/contracts/evidence-bundle.schema.json)
- [Workflow schema](specs/001-mergegate-control-plane/contracts/workflow.schema.json)
