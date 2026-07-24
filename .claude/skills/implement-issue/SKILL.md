---
name: implement-issue
description: >-
  End-to-end workflow to fully implement and close a GitHub issue with spec-kit
  and test-driven development, then ship it as a pull request. Use this whenever
  the user points at a GitHub issue and wants it done — phrases like "implement
  issue 72", "close #74", "do T072", "take this issue to a PR", "finish this
  task with TDD", or "implement the issue using spec-kit". Each issue maps to a
  single task (T0xx) in the feature's tasks.md; the skill locates that task,
  writes failing tests first, implements until green, then commits and pushes a
  PR that closes the issue. Trigger it even when the user only gives an issue
  number or a T-ID and doesn't spell out "spec-kit" or "TDD" — those are the
  house rules for closing any issue in this repo. Do NOT use it for planning a
  brand-new feature from scratch (use speckit-specify/plan/tasks) or for
  reviewing an existing PR.
---

# Implement a GitHub issue with spec-kit + TDD

This skill takes one GitHub issue from "open" to "merged-ready PR" the way this
repo expects every issue to be closed: grounded in the existing spec-kit design
artifacts, driven by tests written *before* the implementation, and landed on a
clean branch whose commits and PR carry **no tool attribution** — the history is
the user's own.

Each issue in this repo is a single task from the feature's `tasks.md`. The
issue title starts with the task ID (e.g. `T072: Frontend component tests …`),
which is your anchor into all the design context. You are implementing that one
task well — not re-planning the feature.

## Why the steps are the way they are

The constitution and spec for this project mandate **red-before / green-after**
TDD: a test that encodes the acceptance criteria must exist and fail for the
right reason *before* the code that satisfies it. This is what makes each task an
independently trustworthy increment. The clean-authorship rule matters because
the user wants their git history to read as their own work against their own
conventions — tool attribution is noise they've asked to never appear. Treat
both as hard requirements, not preferences.

## Workflow

Work through these in order. Keep a short todo list so nothing is skipped.

### 1. Resolve the issue and its task

```bash
gh issue view <N> --json number,title,body,labels,url
```

Read the title and body. Extract the task ID (the leading `T0xx`). The body's
labels (e.g. `owner: frontend`, `phase: polish`) tell you which part of the
codebase you're in.

### 2. Load the spec-kit context

Find the active feature directory under `specs/` (there is normally one, e.g.
`specs/001-mergegate-control-plane/`). Then:

- Open `tasks.md` and locate the exact task line for the T-ID. Note its file
  paths, `[P]` marker, and user-story tag (e.g. `US4`).
- Read the design docs the task depends on: the relevant sections of `spec.md`
  (the user story and its acceptance criteria), `plan.md` (layout, stack,
  conventions), and any of `data-model.md`, `contracts/`, `research.md`,
  `quickstart.md` that the task touches.
- Read `.specify/memory/constitution.md` for the project's non-negotiables
  (TDD, reliability suite, naming, tooling).

Do not invent scope. The task line plus the story's acceptance criteria define
"done." If the task is genuinely ambiguous or its dependencies are unbuilt, stop
and tell the user rather than guessing.

### 3. Branch off the default branch

The PR must merge into the default branch for `Closes #N` to auto-close the
issue, so branch from there:

```bash
git switch main && git pull --ff-only
git switch -c <task-id>-<short-slug>     # e.g. t072-frontend-component-tests
```

Use a lowercase, hyphenated slug derived from the task description.

### 4. Red — write the failing test(s) first

Translate the task's acceptance criteria into concrete tests **before** touching
implementation code. Put them where the task and `plan.md` say they belong
(`backend/tests/…`, `frontend/tests/…`, etc.).

Run them and confirm they fail — and that they fail for the *right* reason (the
behavior is missing), not because of a typo or import error:

```bash
# backend
uv run pytest <path-to-new-tests> -q
# frontend
npm --prefix frontend test -- <path>
```

Match whatever the repo already uses; check `pyproject.toml` / `package.json`
for the real test commands before assuming.

Optionally make this the first commit so the red state is visible in history
(see step 7 for the message rules). A separate red commit is encouraged but not
required.

### 5. Green — implement the minimum to pass

Write the smallest correct implementation that turns the tests green. Follow the
patterns already in the touched files — naming, structure, and idioms from
`plan.md` and the surrounding code. Re-run the task's tests until they pass.

### 6. Refactor and verify the whole surface

Clean up while keeping tests green, then run the full relevant suite plus the
project's quality gates so you don't regress anything:

```bash
# backend
uv run pytest -q
uv run ruff format . && uv run ruff check . --fix
uv run pyright
# frontend
npm --prefix frontend test
npm --prefix frontend run lint
```

Everything must be green before you commit. If a gate fails, fix it — a red gate
is not "done."

### 7. Commit — clean history, no tool attribution

This is a hard rule: **commits must never mention Claude, "co-authored-by", "AI",
or the tool used.** The author is the repo's configured git user, never a
tool identity. Do not pass `--author`, do not add a `Co-Authored-By` trailer, do
not add "Generated with…" lines.

Write a concise conventional-commit subject describing the change, and add the
issue trailer this repo uses:

```bash
git commit -m "feat(frontend): component tests for canvas, inspector, console, evidence" \
  --trailer "Github-Issue:#<N>"
```

Use the type that fits (`feat`, `fix`, `test`, `docs`, `refactor`, `chore`). If
the issue is a bug fix reported by someone, also add
`--trailer "Reported-by:<name>"`.

Then **verify** the commit is clean before pushing — this catch is cheap and the
mistake is hard to undo once pushed:

```bash
git log -1 --format='author=%an <%ae>%n%n%B' | grep -iE 'claude|co-authored|generated with|anthropic' \
  && echo "!! ATTRIBUTION LEAK — amend before pushing" || echo "clean"
```

If it prints the warning, `git commit --amend` to strip the offending lines
before continuing.

### 8. Push and open the PR

```bash
git push -u origin <branch>
```

Open a PR **targeting the default branch** so the issue auto-closes on merge.
The body must contain `Closes #<N>` and must also be free of tool attribution:

```bash
gh pr create --base main --head <branch> \
  --title "<same spirit as the commit subject>" \
  --body "$(cat <<'EOF'
## What
<one-paragraph description of the problem this task solves and how>

## How
- <key implementation points, at a high level>

## Tests
- <the tests added and what they assert; note red-before / green-after>

Closes #<N>
EOF
)"
```

Follow the repo's PR conventions for reviewers and labels (see the project's
guidelines / `CLAUDE.md`). Keep the description focused on the problem and the
approach — no line-by-line code narration, and no mention of any tool.

Note on auto-close: GitHub only auto-closes the issue when a PR whose body says
`Closes #N` is merged into the **default** branch. If the user asks you to base
the PR on a feature integration branch instead, keep `Closes #N` in the body but
tell them the issue won't auto-close until that branch reaches the default
branch — offer `gh issue close <N>` as an explicit fallback once merged.

### 9. Report

Give the user the PR URL, a one-line summary of what shipped, and the test
evidence (what was red, what is now green). If any gate could not be made to
pass, say so plainly rather than implying success.

## Guardrails

- **Never fabricate green.** If tests or gates fail and you can't fix them within
  the task's scope, stop and report — do not push a PR that claims completion.
- **Stay in scope.** Implement the one task the issue names. If you notice
  adjacent work, mention it or flag it as a follow-up; don't fold it in.
- **Confirm before force-pushing or retargeting** an existing branch/PR — those
  are hard to undo. A first push of a fresh branch is part of the normal flow.
- **No tool attribution anywhere** — commits, PR title, PR body, or branch name.
  This is the rule the user cares about most; the verification in step 7 exists
  because it's easy to reintroduce by habit.
