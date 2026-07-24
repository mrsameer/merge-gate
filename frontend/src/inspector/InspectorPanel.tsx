// Minimal run-control inspector (T030). When the Input node is selected it
// drives the contract-before-code lifecycle from the UI: enter an objective
// and create a run, generate/edit/approve its criteria, then start the run.
// Any other selected node shows a read-only summary. All REST calls go
// through the shared api client (../api); shared state lives in ../state/store.

import { useState } from "react";
import { createApiClient } from "../api";
import type { ApiClient, Budget } from "../api";
import { DEFAULT_WORKFLOW } from "../canvas/defaultWorkflow";
import type { WorkflowNode } from "../canvas/types";
import { useAppStore } from "../state/store";
import "./InspectorPanel.css";

const DEFAULT_WORKFLOW_ID = DEFAULT_WORKFLOW.id;
const DEFAULT_REPO_REF = "demo-repo";
const DEFAULT_BUDGETS: Budget = {
  max_attempts: 3,
  max_wall_clock_s: 600,
  max_model_calls: 20,
};

const defaultClient = createApiClient();

export interface InspectorPanelProps {
  client?: ApiClient;
}

export function InspectorPanel({
  client = defaultClient,
}: InspectorPanelProps) {
  const selectedNodeId = useAppStore((s) => s.selectedNodeId);
  const node = DEFAULT_WORKFLOW.nodes.find((n) => n.id === selectedNodeId);

  return (
    <aside
      className="inspector-panel"
      data-testid="inspector-panel"
      aria-label="Node inspector"
    >
      {!node && <p>Select a node to inspect its settings.</p>}
      {node && node.type !== "Input" && <NodeDetails node={node} />}
      {node && node.type === "Input" && <InputNodeInspector client={client} />}
    </aside>
  );
}

function NodeDetails({ node }: { node: WorkflowNode }) {
  return (
    <div className="inspector-section" data-testid="node-details">
      <h2>{node.name}</h2>
      <dl className="inspector-details">
        <dt>Type</dt>
        <dd>{node.type}</dd>
        <dt>Status</dt>
        <dd>{node.status}</dd>
      </dl>
    </div>
  );
}

function InputNodeInspector({ client }: { client: ApiClient }) {
  const objective = useAppStore((s) => s.objective);
  const setObjective = useAppStore((s) => s.setObjective);
  const runId = useAppStore((s) => s.runId);
  const run = useAppStore((s) => s.run);
  const contract = useAppStore((s) => s.contract);
  const setRun = useAppStore((s) => s.setRun);
  const setContract = useAppStore((s) => s.setContract);
  const setCriteria = useAppStore((s) => s.setCriteria);

  const [repoRef, setRepoRef] = useState(DEFAULT_REPO_REF);
  const [provider, setProvider] = useState("scripted");
  const [model, setModel] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const guard = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const handleCreateRun = () =>
    guard(async () => {
      const created = await client.createRun({
        workflow_id: DEFAULT_WORKFLOW_ID,
        objective,
        repo_ref: repoRef,
        provider,
        ...(model.trim() ? { model: model.trim() } : {}),
        budgets: DEFAULT_BUDGETS,
      });
      setRun(created);
    });

  const handleGenerate = () =>
    guard(async () => {
      if (!runId) return;
      setNotice(null);
      const result = await client.generateCriteria(runId, "hybrid");
      if ("criteria" in result) {
        setContract(result);
      } else {
        setNotice(`Clarification needed: ${result.clarification.reason}`);
      }
    });

  const handleSaveCriteria = () =>
    guard(async () => {
      if (!runId || !contract) return;
      const updated = await client.updateCriteria(runId, contract.criteria);
      setContract(updated);
    });

  const handleApprove = () =>
    guard(async () => {
      if (!runId) return;
      const approved = await client.approveCriteria(runId);
      setContract(approved);
    });

  const handleStart = () =>
    guard(async () => {
      if (!runId) return;
      const started = await client.startRun(runId);
      setRun(started);
    });

  const handleRefreshStatus = () =>
    guard(async () => {
      if (!runId) return;
      setRun(await client.getRun(runId));
    });

  const handleApproveMerge = () =>
    guard(async () => {
      if (!runId) return;
      setRun(await client.decideGate(runId, "final", "approve"));
    });

  const updateCriterion = (index: number, command: string) => {
    if (!contract) return;
    setCriteria(
      contract.criteria.map((c, i) => (i === index ? { ...c, command } : c)),
    );
  };

  const approved = contract?.approved ?? false;

  return (
    <div className="inspector-section">
      <h2>Run objective</h2>

      <label className="inspector-field">
        <span>Objective</span>
        <textarea
          aria-label="Objective"
          value={objective}
          rows={3}
          disabled={runId !== null}
          onChange={(e) => setObjective(e.target.value)}
        />
      </label>

      <label className="inspector-field">
        <span>Repository</span>
        <input
          aria-label="Repository"
          value={repoRef}
          disabled={runId !== null}
          onChange={(e) => setRepoRef(e.target.value)}
        />
      </label>

      <label className="inspector-field">
        <span>Provider</span>
        <select
          aria-label="Provider"
          value={provider}
          disabled={runId !== null}
          onChange={(e) => setProvider(e.target.value)}
        >
          <option value="scripted">Scripted demo</option>
          <option value="anthropic">Claude Code</option>
          <option value="gemini">Gemini CLI</option>
          <option value="cursor">Cursor</option>
        </select>
      </label>

      <label className="inspector-field">
        <span>Model</span>
        <input
          aria-label="Model"
          value={model}
          placeholder={provider === "gemini" ? "gemini-2.5-pro" : "Default"}
          disabled={
            runId !== null || provider === "scripted" || provider === "cursor"
          }
          onChange={(e) => setModel(e.target.value)}
        />
      </label>

      <button
        type="button"
        onClick={handleCreateRun}
        disabled={busy || runId !== null || objective.trim() === ""}
      >
        Create run
      </button>

      {run && (
        <p className="inspector-status" data-testid="inspector-run-status">
          Run {run.id} — {run.status}
        </p>
      )}

      <h2>Success criteria</h2>

      <button
        type="button"
        onClick={handleGenerate}
        disabled={busy || runId === null}
      >
        Generate criteria
      </button>

      {notice && <p className="inspector-notice">{notice}</p>}

      {contract && (
        <>
          <ul className="inspector-criteria" data-testid="criteria-list">
            {contract.criteria.map((criterion, index) => (
              <li key={criterion.id} className="inspector-criterion">
                <div className="inspector-criterion__meta">
                  <span className="inspector-criterion__id">
                    {criterion.id}
                  </span>
                  <span className="inspector-criterion__type">
                    {criterion.type} (p{criterion.priority})
                  </span>
                </div>
                <input
                  aria-label={`Command for ${criterion.id}`}
                  value={criterion.command ?? ""}
                  disabled={approved}
                  onChange={(e) => updateCriterion(index, e.target.value)}
                />
              </li>
            ))}
          </ul>

          <div className="inspector-actions">
            <button
              type="button"
              onClick={handleSaveCriteria}
              disabled={busy || approved}
            >
              Save criteria
            </button>
            <button
              type="button"
              onClick={handleApprove}
              disabled={busy || approved}
            >
              {approved ? "Approved" : "Approve criteria"}
            </button>
          </div>
        </>
      )}

      <h2>Run</h2>
      <button type="button" onClick={handleStart} disabled={busy || !approved}>
        Start run
      </button>
      {runId && (
        <button type="button" onClick={handleRefreshStatus} disabled={busy}>
          Refresh run status
        </button>
      )}
      {approved &&
        run?.status === "awaiting_gate" &&
        run.current_attempt > 0 && (
          <button type="button" onClick={handleApproveMerge} disabled={busy}>
            Approve merge
          </button>
        )}

      {error && (
        <p
          className="inspector-error"
          role="alert"
          data-testid="inspector-error"
        >
          {error}
        </p>
      )}
    </div>
  );
}
