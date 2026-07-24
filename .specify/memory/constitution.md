<!--
SYNC IMPACT REPORT
Version change: (template) → 1.0.0
Ratification: initial adoption of the MergeGate constitution.
Modified principles: none (initial creation; all five principles new).
Added sections:
  - Core Principles I–V
  - Configurability & Integrity Constraints
  - Development Workflow & Quality Gates
  - Governance
Removed sections: none.
Templates reviewed for consistency:
  - .specify/templates/plan-template.md ✅ reviewed — "Constitution Check" gate references this file generically; principles below are the gate criteria.
  - .specify/templates/spec-template.md ✅ reviewed — no mandatory-section conflicts; spec already reflects these principles.
  - .specify/templates/tasks-template.md ✅ reviewed — task categories (tests, integrity, policy) align with principles.
  - .claude/skills/speckit-*/SKILL.md ✅ reviewed — no agent-specific naming conflicts requiring edits.
Follow-up TODOs: none.
-->

# MergeGate Constitution

MergeGate is a visual control plane for autonomous coding: models propose changes and
deterministic evidence decides whether they advance. This constitution encodes the
non-negotiables that make a run trustworthy. It governs the product's behavior, its
specifications, and its implementation.

## Core Principles

### I. Generation Is Not Acceptance (NON-NEGOTIABLE)

Creation and acceptance MUST be performed by two separate processes. The execution agent
MAY only assert "I think it is done"; it MUST NOT compute, set, or alter the verdict. The
acceptance verdict MUST be produced by a deterministic engine that reads files, commands,
and exit codes — never a model opinion. A model-based judge MAY provide advisory input for
qualitative rubric items ONLY, and MUST NEVER flip or override a deterministic result.

**Rationale**: The core failure of current coding agents is that they are allowed to grade
their own work. Separating creation from acceptance is the product's entire reason to exist.

### II. Deterministic, Replayable Acceptance (NON-NEGOTIABLE)

Identical recorded state MUST produce an identical verdict. Acceptance input is defined as
`commit SHA + validation config + tool versions + environment fingerprint`. A completed
verdict MUST be replayable from that state with zero model calls and yield the same result.
For every task-specific acceptance test, the system MUST demonstrate a genuine baseline
failure before the change (red) and a pass after the change (green); the baseline failure
MUST be real and MUST NEVER be faked.

**Rationale**: "Can the same state give a different verdict?" must be answerable with a hard
"no." Replay is the crispest possible proof that a green check means something.

### III. Proof-Carrying Runs (NON-NEGOTIABLE)

Every run MUST record all events in an append-only, hash-chained ledger (each entry stores
the previous entry's hash) so that altering any prior entry is detectable. Every completed
run MUST export a single evidence bundle containing the contract, plan, diff, commands with
exit codes, red→green evidence, policy results, retries, acceptance hash, cost, time, and
terminal state. Any verdict MUST be traceable to the exact files, commands, and exit codes
that produced it, with no missing links.

**Rationale**: Trust requires inspectable, tamper-evident receipts — not a green checkmark
with no command output behind it.

### IV. Bounded Autonomy With Clean Rollback (NON-NEGOTIABLE)

Autonomy MUST be bounded by configurable attempt, wall-clock, and model-call budgets, and by
a no-progress detector (same failure signature across consecutive attempts with no material
diff change). On exhaustion or no-progress, the system MUST roll the repository back to a
green baseline, discard the attempt workspace, and produce an honest "undelivered" report.
Every run MUST end in an explicit terminal state, and an exception, crash, or timeout MUST
NEVER be classified as success. Terminal states: `SUCCESS`, `CLARIFICATION_REQUIRED`,
`HUMAN_REJECTED`, `EXHAUSTED`, `NO_PROGRESS`, `TIMED_OUT`, `POLICY_BLOCKED`, `CANCELLED`.

**Rationale**: A system that knows when to stop and can roll back clean is more trustworthy
than one that maximizes autonomous activity.

### V. Failure Drives the Next Attempt; Clarify, Don't Guess (NON-NEGOTIABLE)

A failed check MUST be converted into structured feedback (criterion, command, exit code,
failure signature, first failing location, attempt number) and fed into the next attempt — a
retry counter without real feedback is prohibited. When criteria are contradictory or
ambiguous, the system MUST emit a structured clarification request and halt in
`CLARIFICATION_REQUIRED` rather than guessing or fabricating progress.

**Rationale**: Bounded autonomy is only meaningful if failure changes behavior and the system
refuses to proceed against an impossible contract.

## Configurability & Integrity Constraints

- **Contract before code**: Success criteria MUST be defined (user-defined, agent-generated,
  or hybrid — hybrid is the default), human-reviewed, editable, prioritizable, and explicitly
  approved before any code change. The approved contract MUST be frozen for the run.
- **No hardcoded paths**: The workflow MUST be data, not code. Graph nodes and success/failure
  paths MUST be authored visually and MUST be exportable/importable as YAML or JSON that fully
  reproduces and reruns the loop.
- **Provider not hardcoded**: The coding harness MUST sit behind a provider adapter interface;
  provider and model family MUST be selectable via configuration, and a compatible provider
  MUST be substitutable without changing the workflow definition.
- **Anti-cheat is enforced, not advisory**: Protected paths MUST NOT be modifiable by the
  agent, and forbidden diff patterns MUST be rejected with the offending path/pattern named;
  violations map to `POLICY_BLOCKED`.
- **Isolation per attempt**: Each attempt MUST run in a disposable, isolated workspace so a
  failed or abandoned attempt can be discarded without polluting the base repository.

## Development Workflow & Quality Gates

- **Spec-driven**: Work follows the Spec Kit flow — constitution → specify → (clarify) → plan
  → tasks → implement. Every feature MUST have a spec whose requirements and success criteria
  are technology-agnostic; implementation decisions live in plans, not in the spec.
- **Constitution Check**: The `/speckit-plan` Constitution Check gate MUST verify a design
  against Principles I–V before implementation. A violation MUST be resolved or explicitly
  justified in Complexity Tracking; unjustified violations block the plan.
- **Red-before/green-after discipline**: Task-specific acceptance tests MUST be shown failing
  on the baseline before being accepted as passing after the change.
- **Reliability before polish**: The ten-scenario reliability suite (2-attempt success;
  invalid command; agent timeout; human rejection; manual stop; protected-file edit blocked;
  exhausted attempts; contradictory criteria → clarification; mid-run client refresh; backend
  restart or documented limitation) MUST pass or be documented before feature freeze.
- **The demo is a deliverable**: The end-to-end story MUST remain demonstrable within 5–7
  minutes, and `main` MUST never be left broken.

## Governance

This constitution supersedes other practices for MergeGate. Amendments MUST be documented in
the Sync Impact Report at the top of this file, version-bumped per the policy below, and
propagated to dependent templates (`plan-template.md`, `spec-template.md`, `tasks-template.md`)
and command guidance in the same change.

**Versioning policy** (semantic):
- **MAJOR**: Backward-incompatible governance changes or removal/redefinition of a principle.
- **MINOR**: A new principle or section, or materially expanded guidance.
- **PATCH**: Clarifications, wording, or non-semantic refinements.

**Compliance**: Specs, plans, and implementations MUST be reviewable against Principles I–V.
Any deviation MUST be justified in writing and, for plans, recorded under Complexity Tracking.
The five NON-NEGOTIABLE principles are not subject to per-feature waiver; they may only be
changed by amending this constitution.

**Version**: 1.0.0 | **Ratified**: 2026-07-24 | **Last Amended**: 2026-07-24
