import { useEffect, useState, type ChangeEvent } from "react";
import {
  ApiError,
  createApiClient,
  type ApiClient,
  type Workflow as ApiWorkflow,
} from "../api";
import { fromApiWorkflow, toApiWorkflow } from "../canvas/workflowIO";
import { useAppStore } from "../state/store";

const defaultClient = createApiClient();

export type DownloadWorkflow = (
  filename: string,
  content: string,
  mediaType: string,
) => void;

function downloadWorkflow(
  filename: string,
  content: string,
  mediaType: string,
) {
  const url = URL.createObjectURL(new Blob([content], { type: mediaType }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export interface TopBarProps {
  client?: ApiClient;
  onDownload?: DownloadWorkflow;
}

export function TopBar({
  client = defaultClient,
  onDownload = downloadWorkflow,
}: TopBarProps) {
  const workflow = useAppStore((state) => state.workflow);
  const positions = useAppStore((state) => state.positions);
  const renameWorkflow = useAppStore((state) => state.renameWorkflow);
  const setWorkflow = useAppStore((state) => state.setWorkflow);
  const run = useAppStore((state) => state.run);
  const runId = useAppStore((state) => state.runId);
  const contract = useAppStore((state) => state.contract);
  const setRun = useAppStore((state) => state.setRun);
  const [format, setFormat] = useState<"yaml" | "json">("yaml");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId || !run || !["running", "paused"].includes(run.status)) return;
    const timer = window.setInterval(() => {
      void client
        .getRun(runId)
        .then(setRun)
        .catch((reason: unknown) =>
          setError(reason instanceof Error ? reason.message : String(reason)),
        );
    }, 500);
    return () => window.clearInterval(timer);
  }, [client, run, runId, setRun]);

  const guard = async (operation: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await operation();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  };

  const persistWorkflow = async (): Promise<ApiWorkflow> => {
    let payload = toApiWorkflow(workflow);
    let saved: ApiWorkflow;
    try {
      saved = await client.updateWorkflow(payload.id, payload);
    } catch (reason) {
      if (!(reason instanceof ApiError) || reason.status !== 404) throw reason;
      const created = await client.createWorkflow({
        name: payload.name,
        template: "four_role_loop",
      });
      payload = { ...payload, id: created.id };
      saved = await client.updateWorkflow(created.id, payload);
    }
    setWorkflow(fromApiWorkflow(saved), positions);
    return saved;
  };

  const save = () =>
    guard(async () => {
      await persistWorkflow();
      setNotice("Workflow saved");
    });

  const exportConfig = () =>
    guard(async () => {
      const saved = await persistWorkflow();
      const content = await client.exportWorkflow(saved.id, format);
      onDownload(
        `${saved.id}.${format}`,
        content,
        format === "yaml" ? "application/yaml" : "application/json",
      );
      setNotice(`Exported ${format.toUpperCase()}`);
    });

  const importConfig = (event: ChangeEvent<HTMLInputElement>) =>
    guard(async () => {
      const file = event.target.files?.[0];
      if (!file) return;
      const importedFormat = file.name.toLowerCase().endsWith(".json")
        ? "json"
        : "yaml";
      const imported = await client.importWorkflow(
        await file.text(),
        importedFormat,
      );
      setWorkflow(fromApiWorkflow(imported));
      setNotice(`Imported ${file.name}`);
      event.target.value = "";
    });

  const invokeRunControl = (
    operation: (id: string) => ReturnType<ApiClient["getRun"]>,
  ) =>
    guard(async () => {
      if (!runId) return;
      setRun(await operation(runId));
    });

  const canStart =
    Boolean(runId && contract?.approved) &&
    run?.status === "awaiting_gate" &&
    run.current_attempt === 0;
  const canPause = run?.status === "running";
  const canResume = run?.status === "paused";
  const canStop = canPause || canResume;

  return (
    <header className="top-bar" data-testid="top-bar">
      <label>
        <span className="sr-only">Workflow name</span>
        <input
          className="top-bar__workflow-name"
          aria-label="Workflow name"
          value={workflow.name}
          onChange={(event) => renameWorkflow(event.target.value)}
        />
      </label>
      <div className="top-bar__controls">
        <button type="button" onClick={save} disabled={busy}>
          Save
        </button>
        <label>
          <span className="sr-only">Export format</span>
          <select
            aria-label="Export format"
            value={format}
            onChange={(event) =>
              setFormat(event.target.value as "yaml" | "json")
            }
          >
            <option value="yaml">YAML</option>
            <option value="json">JSON</option>
          </select>
        </label>
        <button type="button" onClick={exportConfig} disabled={busy}>
          Export
        </button>
        <label className="top-bar__import">
          Import
          <input
            type="file"
            aria-label="Import workflow"
            accept=".yaml,.yml,.json,application/yaml,application/json"
            onChange={importConfig}
            disabled={busy}
          />
        </label>
        <button
          type="button"
          onClick={() => invokeRunControl(client.startRun)}
          disabled={busy || !canStart}
        >
          Run
        </button>
        <button
          type="button"
          onClick={() => invokeRunControl(client.pauseRun)}
          disabled={busy || !canPause}
        >
          Pause
        </button>
        <button
          type="button"
          onClick={() => invokeRunControl(client.resumeRun)}
          disabled={busy || !canResume}
        >
          Resume
        </button>
        <button
          type="button"
          onClick={() => invokeRunControl(client.stopRun)}
          disabled={busy || !canStop}
        >
          Stop
        </button>
      </div>
      <span className="top-bar__status" data-testid="run-status">
        {run?.status ?? "idle"}
      </span>
      <span className="top-bar__attempt-counter" data-testid="attempt-counter">
        Attempt {run?.current_attempt ?? 0} /{" "}
        {run?.budgets.max_attempts ?? contract?.criteria.length ?? 0}
      </span>
      {notice && (
        <span className="top-bar__notice" role="status">
          {notice}
        </span>
      )}
      {error && (
        <span className="top-bar__error" role="alert">
          {error}
        </span>
      )}
    </header>
  );
}
