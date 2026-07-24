# Six-minute Track B demo

This is a timed operator script, not a promise that an external model will
respond within six minutes. Use the `Scripted demo` provider for the judged,
reproducible path. The script deliberately shows three distinct outcomes:

- a real baseline-red/result-green proof followed by operator-approved
  `SUCCESS`;
- a failed execution attempt that becomes structured feedback and then a
  truthful `NO_PROGRESS` safe stop;
- a contradictory run that ends in `CLARIFICATION_REQUIRED` before execution.

The baseline red is not a failed execution attempt. It is the required proof
that a task-specific test detects the missing behavior on unchanged code.

## Before the clock

1. Start MergeGate with the [local or Docker instructions](../README.md).
2. Verify the API health endpoint and open <http://localhost:5173>.
3. Keep these files ready to import:
   - [`default-four-role-workflow.yaml`](../demo-repo/fixtures/default-four-role-workflow.yaml)
   - [`contradictory-task-workflow.yaml`](../demo-repo/fixtures/contradictory-task-workflow.yaml)
4. Open three browser tabs. Use the first for success, the second for a
   controlled retry/safe stop, and the third for clarification. Import the
   appropriate fixture only when the script says so.
5. Keep this objective in the clipboard:

   > Add idempotent order creation to POST /orders. Require an Idempotency-Key
   > header. Same key and same body returns the original order without another
   > row. Same key and different body returns HTTP 409. Add tests and OpenAPI
   > docs. Do not modify app/auth.

If a command or provider fails, show the failure as-is. Never approve the final
gate without a passing verdict, and never label unavailable evidence as proof.

## [0:00–0:35] State the trust claim

**Say:** “MergeGate lets a coding provider propose changes, but executable
evidence decides whether they advance.”

Open the [architecture diagram](architecture.md). Point from the harness to the
disposable worktree, then from the worktree through the LLM-free acceptance
engine to the verdict. Highlight that there is no harness-to-verdict edge.

Return to the first UI tab and identify the top bar, node library, graph,
inspector, and run console.

## [0:35–1:10] Configure and save the four-role loop

Import the default fixture. Select Success Criteria, Planning, Execution, and
Validator in turn; show that node instructions/provider/model/tools or
validation settings live in the inspector. Point out the failure edge from
Decision back to Planning and both human gates.

Choose YAML, click **Save**, then **Export**. State that the graph and paths are
configuration, not a hardcoded screen.

## [1:10–1:50] Enter the objective and freeze success criteria

Select Input, paste the idempotency objective, leave Repository as `demo-repo`
and Provider as `Scripted demo`, then click **Create run**.

Click **Generate criteria**. Show that criteria name real repository checks and
commands. Edit one command without changing its meaning (for example add
pytest's `-q`), click **Save criteria**, then **Approve criteria**.

**Say:** “Approval freezes the contract. The coding harness cannot move these
targets while it works.”

## [1:50–2:45] Execute, inspect proof, and approve success

Click **Start run**. Show the running status and attempt counter. When the run
reaches the final gate, open Evidence:

- baseline is `FAILED`;
- result is `PASSED`;
- verdict is `VALID PROOF`;
- test, baseline, result, and `acceptance_hash` values are visible.

Explain that the baseline failure is genuine validation on unchanged code, not
a fabricated failed attempt. Inspect the run console and a completed node to
show commands, exit codes, session output, and changed files.

Only after the passing verdict, click **Approve merge**. Confirm terminal state
`SUCCESS` and the branch or patch reference. A passing check without this human
decision is still `awaiting_gate`, not success.

## [2:45–3:25] Replay without the provider

Click **Replay Validation** and show that the verdict and `acceptance_hash`
match. Point to cost accounting and state that replay adds zero model calls.

Open the terminal evidence view/download. Identify the frozen contract, plan,
diff, commands and exit codes, red/green proof, policy results, retries, cost,
terminal state, and hash-chained ledger.

## [3:25–4:50] Make failure drive another attempt

Switch to the second tab and import the default fixture. Create another
scripted run with the same objective and generate criteria.

For `feature-exists`, replace the command with this deliberate failure:

```bash
python -c "import sys; sys.exit(1)"
```

Click **Save criteria**, **Approve criteria**, and **Start run**.

Show attempt 1's real non-zero command result. In the retry event, identify the
criterion, command, exit code, failure signature/location, and attempt number;
that structured feedback is what the next Planning/Execution cycle receives.

The deterministic provider makes no new material progress on attempt 2, so the
same failure is not reported as success. Show terminal `NO_PROGRESS`, the
attempt count, discarded-workspace/undelivered evidence, and the safe stop.

**Say:** “This is the bounded-autonomy path: failure changes the next action,
and repeated non-progress stops honestly.”

## [4:50–5:30] Clarify instead of guessing

Switch to the third tab and import the contradictory fixture. Select Input and
enter:

> POST /orders must return both 200 and 201 for the same successful request.

Create the scripted run, generate and approve criteria, then start it.

Show `CLARIFICATION_REQUIRED`, attempt 0, the conflicting criterion, skipped
execution/validation, and “No execution attempt was created.” This run makes
zero model calls and must not expose a success claim or completion evidence.

## [5:30–6:00] Close on the receipts

Return to the successful tab and summarize:

1. humans froze the contract and controlled the final gate;
2. the provider proposed an isolated diff;
3. deterministic checks produced the verdict and `acceptance_hash`;
4. failure became structured retry feedback and then a safe stop;
5. replay used zero model calls; and
6. the ledger/evidence bundle makes every claim inspectable.

End on the terminal state and evidence, not on an agent message.

## Track B coverage

| Beat | Where it appears |
| --- | --- |
| 1 | Objective entered at 1:10–1:50. |
| 2 | Success criteria generated, edited, saved, and approved at 1:10–1:50. |
| 3 | Four named roles and configurable node settings shown at 0:35–1:10. |
| 4 | Workflow saved and exported at 0:35–1:10. |
| 5 | Scripted execution runs against `demo-repo` at 1:50–2:45 and 3:25–4:50. |
| 6 | Real command results, red/green proof, hashes, and evidence shown at 1:50–3:25. |
| 7 | Failed execution attempt becomes structured feedback and another iteration at 3:25–4:50. |
| 8 | Operator-approved `SUCCESS` and the separate `NO_PROGRESS` safe stop are both shown. |
| 9 | Node sessions, commands, exit codes, diff/file changes, retries, and ledger receipts are inspected. |

## Live Gemini variant

For a non-deterministic provider demonstration, follow the
[Vertex ADC setup](../README.md#vertex-ai-gemini-25-flash-in-mumbai), select
`Gemini CLI`, and use `gemini-2.5-flash`. Do this after the reproducible Track B
path, not instead of it.

Report the observed state. A Gemini CLI error, timeout, quota failure, empty
diff, or failed deterministic check is not success. Keep the UI on the truthful
failure/retry/terminal evidence and do not fall back to a prerecorded success
claim.
