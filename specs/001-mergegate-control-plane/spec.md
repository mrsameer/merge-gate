# Feature Specification: MergeGate — Loop Engineering Control Plane

**Feature Branch**: `001-mergegate-control-plane`

**Created**: 2026-07-24

**Status**: Draft

**Input**: User description: "MergeGate — a visual control plane for autonomous coding where models propose changes and deterministic evidence decides whether they advance. Coding agents today are often allowed to grade their own work. MergeGate separates creation from acceptance — agents propose, executable evidence decides — and every run leaves a proof bundle you can replay without calling a model. Proof-carrying runs, acceptance outside the model, failure changes the next action, bounded autonomy with clean rollback, clarify-don't-guess, full inspectable receipts, real coding harness with configurable provider."

## User Scenarios & Testing *(mandatory)*

<!--
  Prioritized as user journeys. P1 stories are the demo spine and the graded
  core: build top-to-bottom, nothing below the line until everything above it
  works. Each story is independently demonstrable to a judge.
-->

### User Story 1 - Run an objective to a trustworthy verdict (Priority: P1)

An operator enters a plain-language coding objective against a real repository. The default loop runs four roles — a **Success Criteria** role that turns the objective into measurable completion criteria (a "contract"), a **Planning** role that creates or revises the implementation plan, an **Execution** role that changes the codebase, and a **Validation** role that decides whether the task is complete and provides evidence when it is not. The operator reviews and approves the contract before any code is written; the Execution role proposes changes in an isolated workspace; and the Validation role's completion decision is computed by a separate deterministic engine — never the Execution agent grading itself. If validation passes it proceeds (through a human gate if required) to task success; if it fails with evidence it returns to the Planning role while attempts remain, otherwise it stops safely. On success the operator approves the final gate and the change is presented as a mergeable branch.

**Why this priority**: This is the product. It demonstrates the single most important claim — generation is separated from acceptance, and an agent's opinion cannot turn a red check green. Without this slice there is no demo.

**Note on the Validation role**: MergeGate fulfils the required Validation Agent role with a deterministic Validator rather than an LLM that grades its own work. The role still does exactly what the loop requires — decide completion and return evidence on failure — but the verdict is computed from files, commands, and exit codes, which is the platform's core integrity claim (see User Story 2).

**Independent Test**: Enter the idempotent-order objective, watch criteria generate, approve the contract, run once, and confirm a deterministic verdict is produced by a process distinct from the coding agent — verifiable by inspecting that the verdict's inputs are files/commands/exit-codes, not a model response.

**Acceptance Scenarios**:

1. **Given** a real repository and a plain-language objective, **When** the operator submits it, **Then** the system produces a contract of measurable, testable criteria grounded in files that actually exist in the repository.
2. **Given** a generated contract, **When** the operator reviews it, **Then** the operator can edit at least one criterion and must explicitly approve before execution begins, and the approved contract is frozen for the run.
3. **Given** an approved contract, **When** the run executes, **Then** the coding agent's changes are produced in an isolated per-attempt workspace and the acceptance verdict is computed by a separate deterministic engine.
4. **Given** all criteria pass, **When** the operator approves the final gate, **Then** the run reaches a `SUCCESS` terminal state and the resulting branch/patch is shown.

---

### User Story 2 - Prove the green means something (validator integrity) (Priority: P1)

For any task-specific acceptance test, the system first runs it against the unchanged baseline and asserts it FAILS, then runs the agent, then runs the exact same test against the changed workspace and accepts only if it PASSES. The completed verdict can be re-computed from recorded state — commit identifier, validation config, tool versions, environment fingerprint — with zero model calls, and yields the identical result.

**Why this priority**: This is the win condition and the differentiator. It is the crispest possible answer to "can the same state give a different verdict?" and to "what stops the agent from faking success?"

**Independent Test**: Run a task where attempt 1 writes acceptance tests plus a minimal stub so the task tests fail for real; confirm the system records a genuine baseline failure and a post-change pass, displays a "VALID PROOF" indicator with test/baseline/result hashes, and reproduces the same verdict on replay without any model call.

**Acceptance Scenarios**:

1. **Given** a task-specific acceptance test, **When** it is run on the baseline before any change, **Then** the system records that at least one relevant test failed as expected, with captured command, exit code, and output.
2. **Given** the agent has changed the workspace, **When** the same tests run again, **Then** acceptance is granted only if they now pass, and the transition is displayed as baseline-red / result-green with an acceptance hash.
3. **Given** a completed run, **When** the operator triggers replay against the recorded state, **Then** the identical verdict is produced with zero model calls.
4. **Given** identical recorded state across two replays, **When** both replays run, **Then** both produce the identical verdict.

---

### User Story 3 - Failure changes the next attempt, within bounds (Priority: P1)

When a check fails, the system converts the failure into structured feedback (which criterion, which command, exit code, failure signature, first failing location, attempt number) and feeds it into the next planning attempt. Autonomy is bounded by attempt, wall-clock, and model-call budgets and by a no-progress detector. On exhaustion the workspace is rolled back to a green baseline and an honest "undelivered" report is produced.

**Why this priority**: Demonstrates real bounded autonomy — a retry counter backed by genuine feedback, not a UI number — and that the system knows when to stop and can roll back clean. This is a graded non-negotiable.

**Independent Test**: Run a task that fails on attempt 1, confirm the next attempt consumes the structured failure feedback and the iteration counter advances; separately, force repeated identical failures and confirm the run stops with a safe terminal state and a discarded workspace.

**Acceptance Scenarios**:

1. **Given** a failed check, **When** the run continues, **Then** the next attempt receives structured feedback naming the failing criterion, command, exit code, and failure location — not a generic "tests failed".
2. **Given** a configured attempt/time/model-call budget, **When** any budget is exhausted, **Then** the run stops and does not continue attempting.
3. **Given** two consecutive attempts with the same failure signature and no material change to the diff, **When** the detector fires, **Then** the run terminates as `NO_PROGRESS`.
4. **Given** a run that cannot deliver, **When** it terminates, **Then** the isolated workspace is discarded, the repository is left at a green baseline, and an honest undelivered report is produced.

---

### User Story 4 - Clarify, don't guess (Priority: P2)

When the objective or generated criteria are internally contradictory or ambiguous, the system detects this and emits a structured clarification request instead of proceeding, reaching a `CLARIFICATION_REQUIRED` terminal state.

**Why this priority**: A graded non-negotiable and a strong demo beat. It shows the system refuses to fabricate progress against an impossible contract.

**Independent Test**: Load a contradictory objective (e.g., "return both 200 and 201 for the same successful request") and confirm the system emits a clarification request and does not attempt execution.

**Acceptance Scenarios**:

1. **Given** a contract containing mutually contradictory criteria, **When** the run is started, **Then** the system halts in `CLARIFICATION_REQUIRED` and presents a structured clarification request describing the conflict.
2. **Given** a clarification is required, **When** the operator inspects it, **Then** no code changes have been attempted and no false progress is reported.

---

### User Story 5 - Anti-cheat policy enforcement (Priority: P2)

The system blocks the agent from gaming the verdict: designated protected paths cannot be modified, and forbidden diff patterns (e.g., skipping tests, disabling linters, trivially-true assertions) are rejected. Violations produce a `POLICY_BLOCKED` outcome with the offending path or pattern named.

**Why this priority**: Directly answers "what stops the agent weakening the tests?" and protects the integrity claim. Depends on the run loop existing (US1–US3).

**Independent Test**: Attempt a change that edits a protected path or introduces a forbidden pattern and confirm it is rejected with the specific violation identified.

**Acceptance Scenarios**:

1. **Given** a set of protected paths, **When** the agent's diff touches any of them, **Then** the change is rejected and the run records `POLICY_BLOCKED` with the offending path.
2. **Given** a set of forbidden diff patterns, **When** any appears in the agent's diff, **Then** the change is rejected and the pattern is named in the evidence.

---

### User Story 6 - Inspectable, exportable, tamper-evident receipts (Priority: P2)

Every run produces an append-only, hash-chained ledger of events — files changed, commands with exit codes, verdicts, retry reasons, model calls, tokens/cost, wall-clock — rendered as a run-console timeline and exportable as a single `evidence-bundle.json` that captures contract, plan, diff, commands, red→green evidence, policy results, retries, acceptance hash, cost, time, and terminal state.

**Why this priority**: The proof-carrying-run promise. Judges must be able to inspect and replay every decision. Depends on prior slices producing the events.

**Independent Test**: Complete a run and export the bundle; confirm each required field is present and that the ledger's hash chain detects tampering if any prior entry is altered.

**Acceptance Scenarios**:

1. **Given** a completed run, **When** the operator exports evidence, **Then** a single bundle is produced containing contract, plan, diff, commands and exit codes, red→green evidence, policy results, retries, acceptance hash, cost, time, and terminal state.
2. **Given** the append-only ledger, **When** any prior entry is modified, **Then** the hash chain no longer verifies, making tampering evident.
3. **Given** a run in progress, **When** the operator views the run console, **Then** the ledger is rendered as a live, ordered timeline.

---

### User Story 7 - Author, configure, run, and inspect the loop visually (Priority: P3)

The core experience is a visual node-graph editor (inspired by tools such as Rivet), not a wizard or a set of separate forms. The operator can add nodes from a small node library (Input, Agent, Command, Validator, Decision, Human Gate, Success, Stop), connect them to define execution order and success/failure paths, select a node to edit only its settings, run the whole graph, and watch each node's status and output. The workflow is a configurable template — the operator can adjust agent instructions, the model/provider per agent, the tools available to each agent, success criteria, validation checks, maximum iterations, failure paths, human-approval points, and completion conditions — not a fixed hardcoded sequence. The main screen presents five areas: a top bar (workflow name; save/export; run/pause/stop; run status; attempt counter), a node-library panel, the graph canvas (each node showing name, type, status, a configuration summary, connection points, and its latest result during a run), a node inspector (only the selected node's relevant settings), and a collapsible run console. The operator can pause, resume, and stop a run.

**Why this priority**: The control-plane surface that makes the system legible and refutes "a chat UI dressed up as autonomy" and "a graph whose paths are hardcoded." Valuable but depends on the underlying loop being real.

**Independent Test**: Build a loop by dragging nodes from the library and connecting them, edit one node's settings in the inspector, run it, watch node statuses/attempt counters update live, click a completed node to inspect what it did, and export/re-import the workflow to reproduce the same graph.

**Acceptance Scenarios**:

1. **Given** the node library, **When** the operator adds nodes and connects them, **Then** the connections define the execution order and the success/failure paths between nodes.
2. **Given** a workflow, **When** it runs, **Then** each node visibly reflects its name, type, status, configuration summary, connection points, attempt number, and latest result as the run progresses.
3. **Given** a selected node, **When** the operator opens the inspector, **Then** only that node's relevant settings are shown and editable (e.g., name, instructions, model, tools, command, validation criteria, retry limit, timeout, success path, failure path).
4. **Given** the run console, **When** the operator clicks a completed or failed node, **Then** the console shows what happened during that node's execution (messages, commands run, files changed, validation evidence, errors, retry reasons, human feedback).
5. **Given** a running workflow, **When** the operator pauses, resumes, or stops, **Then** the run honors the command and reflects the new state.
6. **Given** a workflow, **When** it is exported to configuration and re-imported, **Then** the same graph and node settings are reconstructed and can be rerun.

---

### User Story 8 - Provider is configurable, not hardcoded (Priority: P3)

The coding harness sits behind a provider adapter interface. A default provider drives the demo, and the provider/model family is selectable via configuration rather than being baked into the system. A different provider can be substituted without changing the workflow definition.

**Why this priority**: Answers "provider not hardcoded?" A single wired adapter with the swap story proves the point for the demo; a live second-provider swap is a stretch.

**Independent Test**: Show that the provider is chosen from configuration and that swapping the configured provider changes which harness runs, with no change to the workflow definition.

**Acceptance Scenarios**:

1. **Given** the harness adapter interface, **When** the provider is set in configuration, **Then** that provider drives execution without edits to the workflow graph.
2. **Given** a second compatible provider, **When** it replaces the configured provider, **Then** the same objective can be executed through it.

---

### Edge Cases

- **Faked-first-failure guard**: The baseline failure must be genuine. If the "red before" step cannot be shown to fail for a real reason, the proof is invalid and the run must not claim `VALID PROOF`.
- **Exception vs. success**: An unhandled exception, crash, or timeout must never be classified as `SUCCESS`; it maps to `TIMED_OUT`, `NO_PROGRESS`, or a safe stop.
- **Mid-run client refresh**: If the operator's browser refreshes during a run, the run state and event stream must be recoverable and continue to display correctly.
- **Backend restart mid-run**: Either the run resumes from a checkpoint, or the system reports a clearly-documented limitation rather than silently losing state.
- **Manual stop**: The operator can stop a run at any point; the workspace is cleaned up and the terminal state reflects cancellation.
- **Human rejection at final gate**: If the operator rejects the final gate, the run terminates as `HUMAN_REJECTED` and the change is not merged.
- **Empty or non-actionable objective**: The system requests input rather than fabricating a contract.
- **Agent claims done but checks fail**: The agent asserting completion has no effect on the verdict; only the deterministic engine decides.

## Requirements *(mandatory)*

### Functional Requirements

**Contract & grounding**

- **FR-001**: System MUST convert a plain-language objective into a set of measurable, testable acceptance criteria grounded in files that exist in the target repository.
- **FR-001a**: System MUST support three ways of defining success criteria — **user-defined** (the engineer writes the criteria), **agent-generated** (the agent proposes them), and **hybrid** (the engineer provides the objective and constraints; the agent proposes measurable criteria for approval) — with **hybrid as the default**.
- **FR-001b**: System MUST let the operator review, edit, **prioritize**, and confirm the criteria (including any required human approvals) before execution begins.
- **FR-001c**: System MUST support acceptance criteria including at least: the project builds successfully; existing tests continue to pass; new tests are added; a required file or feature exists; protected files are not modified; coverage reaches a threshold; performance improves against a baseline; public APIs remain compatible; and the implementation follows the requested architecture.
- **FR-002**: System MUST require explicit human approval of the contract before any code changes are executed, and MUST allow the operator to edit criteria before approving.
- **FR-003**: System MUST freeze the approved contract for the duration of the run so that acceptance targets cannot move during execution.

**Separation of generation and acceptance**

- **FR-004**: System MUST execute proposed code changes using a real coding harness with filesystem, shell, and test-execution access.
- **FR-005**: System MUST compute the acceptance verdict in a deterministic engine that is a separate process from the coding agent; the coding agent MUST NOT be able to set or alter the verdict.
- **FR-006**: System MUST produce identical verdicts for identical recorded state (deterministic acceptance).
- **FR-007**: System MUST run acceptance checks in a defined, ordered sequence and capture, for each step, a pass/fail result plus command, exit code, output, and duration.
- **FR-008**: System MAY use a model-based judge ONLY for qualitative rubric items and ONLY as advisory input; such judgment MUST NEVER override or flip a deterministic verdict.

**Validator integrity**

- **FR-009**: For each task-specific acceptance test, System MUST demonstrate a genuine baseline failure before the change and a pass after the change, and MUST record hashes for the test, baseline result, and post-change result.
- **FR-010**: System MUST support replaying a completed verdict from recorded state (commit identifier, validation config, tool versions, environment fingerprint) with zero model calls, producing the identical result.

**Isolation, rollback, bounded autonomy**

- **FR-011**: System MUST run each attempt in an isolated, disposable workspace so that a failed or abandoned attempt can be discarded cleanly.
- **FR-012**: System MUST convert each failed check into structured feedback (criterion, command, exit code, failure signature, first failing location, attempt number) and feed it into the next attempt.
- **FR-013**: System MUST enforce configurable budgets on number of attempts, wall-clock time, and model calls, and MUST stop when any budget is exhausted.
- **FR-014**: System MUST detect no-progress (same failure signature across consecutive attempts with no material change to the diff) and stop safely.
- **FR-015**: On exhaustion or no-progress, System MUST roll the repository back to a green baseline, discard the attempt workspace, and produce an honest undelivered report.

**Clarification**

- **FR-016**: System MUST detect contradictory or ambiguous criteria and emit a structured clarification request, halting in `CLARIFICATION_REQUIRED` without attempting execution.

**Anti-cheat policy**

- **FR-017**: System MUST reject changes that modify designated protected paths.
- **FR-018**: System MUST reject changes containing designated forbidden diff patterns and MUST name the offending path or pattern in the evidence.

**Receipts & evidence**

- **FR-019**: System MUST record all run events in an append-only, hash-chained ledger such that altering any prior entry breaks verification (tamper-evident).
- **FR-020**: System MUST export a single evidence bundle per completed run containing contract, plan, diff, commands with exit codes, red→green evidence, policy results, retries, acceptance hash, cost, time, and terminal state.
- **FR-021**: System MUST render the ledger as a live, ordered run-console timeline during execution.
- **FR-022**: System MUST record model calls, token usage, cost, and wall-clock time for each run.

**Human control & terminal states**

- **FR-023**: System MUST provide pause, resume, and stop controls for an in-progress run.
- **FR-024**: System MUST provide exactly one contract-approval human gate and one final merge human gate.
- **FR-025**: System MUST classify every run into an explicit terminal state and MUST NEVER classify an exception, crash, or timeout as success. Terminal states are: `SUCCESS`, `CLARIFICATION_REQUIRED`, `HUMAN_REJECTED`, `EXHAUSTED`, `NO_PROGRESS`, `TIMED_OUT`, `POLICY_BLOCKED`, `CANCELLED`.

**Control plane surface (visual node-graph editor)**

- **FR-026**: System MUST present the workflow as a canvas of typed nodes (Input, Agent, Command, Validator, Decision, Human Gate, Success, Stop), each showing name, type, status, configuration summary, connection points, attempt number, and latest result.
- **FR-026a**: System MUST let the operator author the graph visually — add nodes from a node library, connect nodes to define execution order, and configure success and failure paths — rather than editing a fixed hardcoded sequence.
- **FR-026b**: System MUST present a main screen with five areas: a top bar (workflow name; save/export; run, pause, stop controls; run status; attempt counter); a node-library panel; the graph canvas; a node inspector; and a collapsible run console.
- **FR-027**: System MUST provide an inspector that shows and edits only the currently selected node's relevant settings (from among: name, instructions, model/provider, tools, command, validation criteria, retry limit, timeout, success path, failure path).
- **FR-028**: System MUST support exporting and importing the workflow as human-readable configuration (YAML or JSON), and the run behavior MUST follow that configuration (paths are data, not hardcoded).
- **FR-028a**: The exported configuration MUST describe the agents, their instructions and tools, the task contract, validation checks, retry limits, workflow transitions, and approval requirements, and MUST be re-importable and rerunnable to reproduce the same loop.

**Loop configurability (template, not hardcoded)**

- **FR-031**: System MUST expose the default loop as a configurable template in which the operator can adjust, per applicable node: agent instructions; model/coding-agent provider; tools available to each agent; success criteria; validation checks; maximum iterations; failure paths; human-approval points; and completion conditions.

**Session inspection**

- **FR-032**: System MUST let the operator inspect what each agent/node did, showing at minimum: agent input, agent output, commands and tools used, files created or changed, validation results, retry reason, and current status.
- **FR-033**: System MUST make the run console collapsible and MUST let the operator click a completed or failed node to inspect what happened during its execution (messages, commands, files changed, validation evidence, errors, retry reasons, human feedback).

**Configurable provider**

- **FR-034**: System MUST access the coding harness through a provider adapter interface, with the provider and model family selected via configuration rather than hardcoded.
- **FR-035**: System MUST allow substituting a different compatible provider without changing the workflow definition.

### Key Entities *(include if feature involves data)*

- **Workflow**: The typed-node graph defining the run's stages and the pass/fail routing between them; exportable/importable as configuration. Its default form is the four-role loop.
- **Agent Role**: One of the four configurable default-loop roles — **Success Criteria** (objective → measurable criteria), **Planning** (create/revise the plan), **Execution** (change the codebase), **Validation** (decide completion and provide evidence on failure) — each with configurable instructions, model/provider, and tools.
- **Run**: A single execution of a workflow against an objective; owns a terminal state, budgets, and the ledger.
- **Attempt**: One iteration within a run, bound to an isolated workspace, a diff, and a set of check results.
- **Contract / Criteria**: The frozen, human-approved set of measurable acceptance criteria; each criterion has a type, a command or assertion, and expected outcomes.
- **Verdict**: The deterministic pass/fail decision for an attempt, with per-check results, exit codes, durations, and an acceptance hash.
- **Evidence Bundle**: The exported proof-carrying record of a completed run.
- **Ledger Entry**: An append-only, hash-chained event record (stores the previous entry's hash) forming the tamper-evident receipt trail.
- **Failure Signature**: A stable identifier derived from failed criteria and normalized error messages, used by the no-progress detector.
- **Provider Adapter**: The configurable interface to a coding harness / model family.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of replays of a completed run's verdict produce the identical result using zero model calls.
- **SC-002**: The acceptance verdict is set by the deterministic engine in 100% of runs; the coding agent sets or alters the verdict in 0% of runs.
- **SC-003**: For every task-specific acceptance test in a successful run, a genuine baseline failure and a post-change pass are both recorded (red-before/green-after coverage = 100% of task tests).
- **SC-004**: 100% of failed checks that lead to a retry are accompanied by structured feedback identifying the criterion, command, exit code, and failure location.
- **SC-005**: No run exceeds its configured attempt, time, or model-call budget; on exhaustion the repository is left at a green baseline in 100% of undelivered runs.
- **SC-006**: A contradictory contract results in `CLARIFICATION_REQUIRED` with zero code-change attempts, 100% of the time.
- **SC-007**: Any change touching a protected path or containing a forbidden pattern is rejected 100% of the time, with the specific violation named.
- **SC-008**: Every completed run exports an evidence bundle containing all required fields, and altering any prior ledger entry is detectable 100% of the time.
- **SC-009**: An observer can trace any single verdict back to the exact files, commands, and exit codes that produced it, with no missing links in the receipt trail.
- **SC-010**: The full end-to-end story — objective → contract → run → first real failure → recovery → success → replay → clarification — is demonstrable within a 5–7 minute walkthrough.
- **SC-011**: The reliability suite of ten scenarios (2-attempt success; invalid command; agent timeout; human rejection; manual stop; protected-file edit blocked; exhausted attempts; contradictory criteria → clarification; mid-run client refresh; backend restart or documented limitation) passes or is documented for 10/10 scenarios.
- **SC-012**: The required Track B demonstration is fully covered — all nine beats are shown: (1) an objective entered; (2) success criteria generated or edited; (3) the four-agent loop configured; (4) the workflow saved/exported; (5) an execution attempt running against a repository; (6) a real validation result with evidence visible; (7) a failed attempt feeding back into another iteration; (8) a later success or a safe stop after attempts are exhausted; (9) agent sessions and file changes inspectable.
- **SC-013**: The default loop runs the four named roles (Success Criteria, Planning, Execution, Validation) and every one of them is configurable (instructions, model/provider, tools, and the loop's criteria, validation checks, max iterations, failure paths, human-approval points, and completion conditions) without editing code.
- **SC-014**: A workflow authored in the UI can be exported to YAML or JSON and re-imported to reproduce and rerun the identical loop, 100% of the time.

## Assumptions

- **Single operator, local/demo scale**: The system targets one operator driving runs in a hackathon/demo setting, not multi-tenant production scale; concurrency, enterprise auth, and horizontal scaling are out of scope for v1.
- **Self-contained demo repository**: Acceptance uses a compact service (a FastAPI order service) whose test suite runs in seconds; the repo and task are created only after the official sprint start. The seed objective is idempotent order creation on `POST /orders` (require `Idempotency-Key`; same key + same body → original order and no new row; same key + different body → HTTP 409; add tests and OpenAPI docs; do not modify the auth module).
- **Deliberate honest first failure**: The demo relies on a genuine TDD red→green flow (attempt 1 writes acceptance tests + a minimal stub that really fails; attempt 2 implements the behavior). The first failure is never faked.
- **Contradictory task kept on hand**: A saved contradictory objective ("return both 200 and 201 for the same successful request") is used to trigger clarification on demand.
- **Locked technical decisions (for the planning phase, not part of user-facing behavior)**: visual canvas via React Flow (`@xyflow/react`); orchestration via LangGraph with durable checkpoints and human-gate interrupts; a FastAPI control plane exposing REST + server-sent events; an append-only run ledger in SQLite + JSONL, hash-chained; per-attempt isolation via git worktrees on feature branches with a command allowlist, timeout, and diff policy; default coding harness via a headless Cursor CLI behind a swappable provider adapter (Claude Agent SDK / Aider / Codex as alternates). These are recorded here so the spec is complete, but the spec's requirements and success criteria remain technology-agnostic.
- **Model/provider available at run time**: Valid API keys/credits and the provided harness access are available and validated before the demo.
- **Bounded budgets are pre-configured**: Attempt count, wall-clock, and model-call budgets are set to demo-appropriate values before a run starts.
- **Twenty CRM integration is a stretch dependency**: Any real-world task against the Twenty CRM codebase is attempted only if the full loop and demo are green well ahead of time, and is not required for the graded core.
- **Criterion evaluators (FR-001c scope)**: The acceptance engine evaluates criteria through a
  pluggable criterion-evaluator interface. v1 ships built-in evaluators for build, lint, existing
  tests, new tests, required-file/feature-exists, protected-paths, coverage-threshold,
  OpenAPI/API-compatibility, migration apply/rollback, duplicate-order, and forbidden-diff. The
  `performance-improves-against-baseline` and `follows-requested-architecture` criterion types are
  supported through the same interface but are demonstrated post-MVP; the seed demo task exercises
  the concrete subset above.
- **Bonus capabilities are optional, not required**: Token/model-call/cost tracking (covered by FR-022), live agent/command streaming, git-worktree/container isolation (covered by FR-011), pause/resume/checkpoint recovery (covered by FR-023), reusable versioned workflow templates, and external-harness/multi-provider integration (covered by FR-034/FR-035) are treated as bonus enhancements layered on top of the required core. Reusable versioned templates specifically are out of scope for the graded core and pursued only as a stretch.
