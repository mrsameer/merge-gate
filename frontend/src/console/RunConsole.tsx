// Collapsible run console (spec.md FR-033, T030). Subscribes to the active
// run's SSE event stream and renders two live views: a per-node status list
// and a scrolling log of every event received. Shared state (runId, events,
// node statuses) lives in ../state/store; the transport is ../state/sseClient,
// injectable via `connect` so tests can drive it without a real EventSource.

import { useEffect } from "react";
import { connectRunEvents } from "../state/sseClient";
import type { RunEventHandlers, RunEventsClient } from "../state/sseClient";
import { useAppStore } from "../state/store";
import "./RunConsole.css";

type ConnectFn = (runId: string, handlers: RunEventHandlers) => RunEventsClient;

const defaultConnect: ConnectFn = (runId, handlers) =>
  connectRunEvents(runId, handlers);

export interface RunConsoleProps {
  collapsed: boolean;
  onToggle: () => void;
  connect?: ConnectFn;
}

export function RunConsole({
  collapsed,
  onToggle,
  connect = defaultConnect,
}: RunConsoleProps) {
  const runId = useAppStore((s) => s.runId);
  const events = useAppStore((s) => s.events);
  const nodeStatuses = useAppStore((s) => s.nodeStatuses);
  const appendEvent = useAppStore((s) => s.appendEvent);
  const applyNodeStatus = useAppStore((s) => s.applyNodeStatus);
  const retry = useAppStore((s) => s.retry);
  const setRetry = useAppStore((s) => s.setRetry);
  const clarification = useAppStore((s) => s.clarification);
  const setClarification = useAppStore((s) => s.setClarification);

  useEffect(() => {
    if (!runId) return;

    const record = (type: string) => (data: unknown) =>
      appendEvent(type, (data ?? {}) as Record<string, unknown>);

    const handlers: RunEventHandlers = {
      node_status: (data) => {
        const payload = data as { node?: string };
        if (payload.node) applyNodeStatus(payload.node, "running");
        record("node_status")(data);
      },
      verdict: (data) => {
        const payload = data as { passed?: boolean };
        applyNodeStatus("validation", payload.passed ? "passed" : "failed");
        record("verdict")(data);
      },
      gate: record("gate"),
      retry: (data) => {
        const payload = data as {
          attempt?: number;
          max_attempts?: number;
          reason?: string;
          feedback?: Record<string, unknown>;
        };
        if (payload.attempt && payload.max_attempts && payload.reason) {
          setRetry({
            attempt: payload.attempt,
            maxAttempts: payload.max_attempts,
            reason: payload.reason,
            feedback: payload.feedback,
          });
        }
        record("retry")(data);
      },
      harness_output: record("harness_output"),
      command_result: record("command_result"),
      policy_block: record("policy_block"),
      terminal: (data) => {
        const payload = data as {
          status?: string;
          clarification?: {
            reason: string;
            conflicting_criteria: string[];
          };
        };
        if (
          payload.status === "CLARIFICATION_REQUIRED" &&
          payload.clarification
        ) {
          setClarification(payload.clarification);
          applyNodeStatus("execution", "skipped");
          applyNodeStatus("validation", "skipped");
        }
        record("terminal")(data);
      },
    };

    const client = connect(runId, handlers);
    return () => client.close();
  }, [
    runId,
    connect,
    appendEvent,
    applyNodeStatus,
    setRetry,
    setClarification,
  ]);

  const statuses = Object.entries(nodeStatuses);

  return (
    <section
      className="run-console"
      data-testid="run-console"
      data-collapsed={collapsed}
      aria-label="Run console"
    >
      <button type="button" onClick={onToggle} aria-expanded={!collapsed}>
        Run console
      </button>

      {!collapsed && (
        <div className="run-console__body">
          {clarification && (
            <section
              className="run-console__clarification"
              data-testid="clarification-request"
              aria-live="assertive"
            >
              <h2>Clarification required</h2>
              <p>{clarification.reason}</p>
              <p>
                Conflicting criteria:{" "}
                <strong>{clarification.conflicting_criteria.join(", ")}</strong>
              </p>
              <p className="run-console__no-attempt">
                No execution attempt was created. Resolve the conflict before
                starting a new run.
              </p>
            </section>
          )}
          {retry && (
            <div className="run-console__retry" aria-live="polite">
              <strong data-testid="attempt-progress">
                Attempt {retry.attempt} / {retry.maxAttempts}
              </strong>
              <span data-testid="retry-reason">
                Retrying because {retry.reason}:{" "}
                {String(retry.feedback?.criterion ?? "acceptance failed")}
                {retry.feedback?.command
                  ? ` (${String(retry.feedback.command)})`
                  : ""}
              </span>
            </div>
          )}
          <ul className="run-console__statuses" data-testid="node-statuses">
            {statuses.length === 0 && <li>No node activity yet.</li>}
            {statuses.map(([node, status]) => (
              <li key={node} data-testid={`node-status-${node}`}>
                <span className="run-console__node">{node}</span>
                <span className="run-console__node-status" data-status={status}>
                  {status}
                </span>
              </li>
            ))}
          </ul>

          <ol className="run-console__timeline" data-testid="event-log">
            {events.length === 0 && <li>No run in progress.</li>}
            {events.map((event) => (
              <li key={event.seq} data-testid={`event-${event.seq}`}>
                <span className="run-console__event-type">{event.type}</span>
                <span className="run-console__event-data">
                  {JSON.stringify(event.data)}
                </span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </section>
  );
}
