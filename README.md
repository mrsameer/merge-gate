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

The shipped backend image includes the locked test tools needed by the bundled
demo acceptance contract, so Compose supports the complete credential-free
scripted proof. It does not install third-party provider CLIs. Use local setup
for Gemini CLI, or extend the backend image explicitly; never describe a
missing CLI as a successful model run.

## Vertex AI Gemini 2.5 Flash in Mumbai

The Gemini adapter runs the installed `gemini` CLI headlessly inside each
attempt worktree. For Vertex AI, authenticate with Application Default
Credentials (ADC); no API key belongs in this repository.

Run the interactive login only when ADC is not already configured:

```bash
gcloud auth application-default login
```

In the shell that starts the backend, set the Vertex routing configuration:

```bash
export GOOGLE_GENAI_USE_VERTEXAI=true
export GOOGLE_CLOUD_PROJECT="your-google-cloud-project"
export GOOGLE_CLOUD_LOCATION=asia-south1
gcloud auth application-default print-access-token >/dev/null

cd backend
uv sync --frozen
uv run uvicorn mergegate.api.main:app --reload --port 8000
```

Start the frontend normally. In the Input inspector choose `Gemini CLI`, set
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
