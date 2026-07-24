// Minimal run-control inspector (T030). When the Input node is selected it
// drives the contract-before-code lifecycle from the UI: enter an objective
// and create a run, generate/edit/approve its criteria, then start the run.
// Any other selected node shows a read-only summary. All REST calls go
// through the shared api client (../api); shared state lives in ../state/store.

import { useState } from "react";
import { createApiClient } from "../api";
import type { ApiClient, Budget } from "../api";
import type { EdgePath, NodeConfig, WorkflowNode } from "../canvas/types";
import { useAppStore } from "../state/store";
import "./InspectorPanel.css";

const DEFAULT_REPO_REF = "demo-repo";
const DEFAULT_BUDGETS: Budget = {
  max_attempts: 3,
  max_wall_clock_s: 1800,
  max_model_calls: 120,
};

const defaultClient = createApiClient();

export interface InspectorPanelProps {
  client?: ApiClient;
}

export function InspectorPanel({
  client = defaultClient,
}: InspectorPanelProps) {
  const selectedNodeId = useAppStore((s) => s.selectedNodeId);
  const node = useAppStore((s) =>
    s.workflow.nodes.find((item) => item.id === selectedNodeId),
  );

  return (
    <aside
      className="inspector-panel"
      data-testid="inspector-panel"
      aria-label="Node inspector"
    >
      {!node && <p>Select a node to inspect its settings.</p>}
      {node && <NodeSettingsEditor node={node} />}
      {node?.type === "Validator" && <PolicyEditor />}
      {node?.type === "Input" && <InputNodeInspector client={client} />}
    </aside>
  );
}

function PolicyEditor() {
  const policy = useAppStore((s) => s.policy);
  const setPolicy = useAppStore((s) => s.setPolicy);

  const parseLines = (value: string) =>
    value
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);

  return (
    <div className="inspector-section" data-testid="policy-editor">
      <h2>Policy guardrails</h2>
      <p className="inspector-notice">
        Checked against every attempt before an acceptance verdict.
      </p>
      <label className="inspector-field">
        <span>Protected paths</span>
        <textarea
          aria-label="Protected paths"
          rows={4}
          value={policy.protected_paths.join("\n")}
          onChange={(event) =>
            setPolicy({
              ...policy,
              protected_paths: parseLines(event.target.value),
            })
          }
        />
      </label>
      <label className="inspector-field">
        <span>Forbidden diff patterns</span>
        <textarea
          aria-label="Forbidden diff patterns"
          rows={4}
          value={policy.forbidden_diff_patterns.join("\n")}
          onChange={(event) =>
            setPolicy({
              ...policy,
              forbidden_diff_patterns: parseLines(event.target.value),
            })
          }
        />
      </label>
    </div>
  );
}

function NodeSettingsEditor({ node }: { node: WorkflowNode }) {
  const nodes = useAppStore((state) => state.workflow.nodes);
  const updateNode = useAppStore((state) => state.updateNode);
  const connectNodes = useAppStore((state) => state.connectNodes);
  const removeNode = useAppStore((state) => state.removeNode);

  const updateConfig = <K extends keyof NodeConfig>(
    key: K,
    value: NodeConfig[K],
  ) => updateNode(node.id, { config: { [key]: value } });

  const updatePath = (path: EdgePath, target: string) => {
    connectNodes(node.id, target, path);
  };

  const hasTimeout = ["Agent", "Command", "Validator"].includes(node.type);
  const hasPaths = [
    "Agent",
    "Command",
    "Validator",
    "Decision",
    "HumanGate",
  ].includes(node.type);

  return (
    <div className="inspector-section" data-testid="node-details">
      <h2>{node.name}</h2>
      <dl className="inspector-details">
        <dt>Type</dt>
        <dd>{node.type}</dd>
        <dt>Status</dt>
        <dd>{node.status}</dd>
      </dl>

      <label className="inspector-field">
        <span>Name</span>
        <input
          aria-label="Node name"
          value={node.name}
          onChange={(event) =>
            updateNode(node.id, { name: event.target.value })
          }
        />
      </label>

      <button
        type="button"
        className="inspector-delete-node"
        onClick={() => removeNode(node.id)}
        aria-label={`Delete node ${node.name}`}
      >
        Delete node
      </button>

      {node.type === "Agent" && (
        <>
          <label className="inspector-field">
            <span>Instructions</span>
            <textarea
              aria-label="Instructions"
              rows={4}
              value={node.config?.instructions ?? ""}
              onChange={(event) =>
                updateConfig("instructions", event.target.value)
              }
            />
          </label>
          <label className="inspector-field">
            <span>Provider</span>
            <select
              aria-label="Node provider"
              value={node.config?.provider ?? ""}
              onChange={(event) => updateConfig("provider", event.target.value)}
            >
              <option value="">Use run default</option>
              <option value="aider">Aider</option>
              <option value="gemini">Gemini</option>
              <option value="anthropic">Claude Code</option>
              <option value="claude-agent-sdk">Claude Agent SDK</option>
              <option value="codex">Codex</option>
              <option value="cursor">Cursor</option>
              <option value="scripted">Scripted</option>
            </select>
          </label>
          <label className="inspector-field">
            <span>Model</span>
            <input
              aria-label="Node model"
              value={node.config?.model ?? ""}
              onChange={(event) => updateConfig("model", event.target.value)}
            />
          </label>
          <label className="inspector-field">
            <span>Tools</span>
            <input
              aria-label="Tools"
              value={(node.config?.tools ?? []).join(", ")}
              placeholder="shell, filesystem"
              onChange={(event) =>
                updateConfig(
                  "tools",
                  event.target.value
                    .split(",")
                    .map((tool) => tool.trim())
                    .filter(Boolean),
                )
              }
            />
          </label>
          <label className="inspector-field">
            <span>Retry limit</span>
            <input
              aria-label="Retry limit"
              type="number"
              min={0}
              value={node.config?.retry_limit ?? 0}
              onChange={(event) =>
                updateConfig("retry_limit", Number(event.target.value))
              }
            />
          </label>
        </>
      )}

      {node.type === "Command" && (
        <label className="inspector-field">
          <span>Command</span>
          <textarea
            aria-label="Command"
            rows={3}
            value={node.config?.command ?? ""}
            onChange={(event) => updateConfig("command", event.target.value)}
          />
        </label>
      )}

      {node.type === "Validator" && (
        <label className="inspector-field">
          <span>Validation criteria</span>
          <textarea
            aria-label="Validation criteria"
            rows={3}
            value={node.config?.criteria_ref ?? ""}
            onChange={(event) =>
              updateConfig("criteria_ref", event.target.value)
            }
          />
        </label>
      )}

      {["Decision", "HumanGate"].includes(node.type) && (
        <label className="inspector-field">
          <span>Completion condition</span>
          <input
            aria-label="Completion condition"
            value={node.config?.completion_condition ?? ""}
            onChange={(event) =>
              updateConfig("completion_condition", event.target.value)
            }
          />
        </label>
      )}

      {hasTimeout && (
        <label className="inspector-field">
          <span>Timeout (seconds)</span>
          <input
            aria-label="Timeout"
            type="number"
            min={1}
            value={node.config?.timeout_s ?? 300}
            onChange={(event) =>
              updateConfig("timeout_s", Number(event.target.value))
            }
          />
        </label>
      )}

      {hasPaths && (
        <>
          <PathSelect
            label="Success path"
            value={node.config?.success_path ?? ""}
            nodes={nodes.filter((item) => item.id !== node.id)}
            onChange={(target) => updatePath("success", target)}
          />
          <PathSelect
            label="Failure path"
            value={node.config?.failure_path ?? ""}
            nodes={nodes.filter((item) => item.id !== node.id)}
            onChange={(target) => updatePath("failure", target)}
          />
        </>
      )}
    </div>
  );
}

function PathSelect({
  label,
  value,
  nodes,
  onChange,
}: {
  label: string;
  value: string;
  nodes: WorkflowNode[];
  onChange: (target: string) => void;
}) {
  return (
    <label className="inspector-field">
      <span>{label}</span>
      <select
        aria-label={label}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">Not configured</option>
        {nodes.map((item) => (
          <option key={item.id} value={item.id}>
            {item.name}
          </option>
        ))}
      </select>
    </label>
  );
}

function InputNodeInspector({ client }: { client: ApiClient }) {
  const workflowId = useAppStore((s) => s.workflow.id);
  const objective = useAppStore((s) => s.objective);
  const setObjective = useAppStore((s) => s.setObjective);
  const runId = useAppStore((s) => s.runId);
  const run = useAppStore((s) => s.run);
  const contract = useAppStore((s) => s.contract);
  const setRun = useAppStore((s) => s.setRun);
  const setContract = useAppStore((s) => s.setContract);
  const setCriteria = useAppStore((s) => s.setCriteria);
  const setClarification = useAppStore((s) => s.setClarification);
  const resetRun = useAppStore((s) => s.resetRun);
  const policy = useAppStore((s) => s.policy);

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
        workflow_id: workflowId,
        objective,
        repo_ref: repoRef,
        provider,
        ...(model.trim() ? { model: model.trim() } : {}),
        policy,
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
        setClarification(null);
        setContract(result);
      } else {
        setClarification(result.clarification);
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

  const handleNewRun = () =>
    guard(async () => {
      if (
        runId &&
        run &&
        ["running", "paused", "awaiting_gate"].includes(run.status)
      ) {
        await client.stopRun(runId);
      }
      setNotice(null);
      resetRun();
    });

  const handleResetRepo = () =>
    guard(async () => {
      setNotice(null);
      const result = await client.resetRepo(run?.repo_ref ?? repoRef);
      const removed = result.removed.length
        ? ` (removed ${result.removed.length} untracked file${
            result.removed.length === 1 ? "" : "s"
          })`
        : "";
      setNotice(
        result.clean
          ? `Reset ${result.repo_ref} to a clean baseline${removed}.`
          : `Reset ran but ${result.repo_ref} is still not clean; check it manually.`,
      );
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
          value={run?.repo_ref ?? repoRef}
          disabled={runId !== null}
          onChange={(e) => setRepoRef(e.target.value)}
        />
      </label>

      <label className="inspector-field">
        <span>Provider</span>
        <select
          aria-label="Provider"
          value={run?.provider ?? provider}
          disabled={runId !== null}
          onChange={(e) => setProvider(e.target.value)}
        >
          <option value="scripted">Scripted demo</option>
          <option value="aider">Aider</option>
          <option value="anthropic">Claude Code</option>
          <option value="claude-agent-sdk">Claude Agent SDK</option>
          <option value="codex">Codex</option>
          <option value="gemini">Gemini CLI</option>
          <option value="cursor">Cursor</option>
        </select>
      </label>

      <label className="inspector-field">
        <span>Model</span>
        <input
          aria-label="Model"
          value={run?.model ?? model}
          placeholder={provider === "gemini" ? "gemini-2.5-flash" : "Default"}
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
      <button
        type="button"
        onClick={handleStart}
        disabled={busy || !approved || run?.status === "CLARIFICATION_REQUIRED"}
      >
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
      {runId && (
        <button
          type="button"
          onClick={handleNewRun}
          disabled={busy}
        >
          New run
        </button>
      )}
      <button
        type="button"
        onClick={handleResetRepo}
        disabled={busy || run?.status === "running"}
        title="Revert tracked edits and remove leftover untracked files so the next run starts from a red baseline"
      >
        Reset demo repo
      </button>

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
