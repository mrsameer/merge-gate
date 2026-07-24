// SSE `EventSource` client for the run event stream, per
// specs/001-mergegate-control-plane/contracts/control-plane-api.md
// (`GET /runs/{id}/events`). Native EventSource already resends
// `Last-Event-ID` on reconnect, which is why research.md picked it over a
// hand-rolled transport — this client only needs to wire named events to
// handlers.

export type RunEventType =
  | "node_status"
  | "harness_output"
  | "command_result"
  | "verdict"
  | "retry"
  | "gate"
  | "policy_block"
  | "terminal";

const RUN_EVENT_TYPES: readonly RunEventType[] = [
  "node_status",
  "harness_output",
  "command_result",
  "verdict",
  "retry",
  "gate",
  "policy_block",
  "terminal",
];

export type RunEventHandlers = {
  [K in RunEventType]?: (data: unknown) => void;
};

export interface ConnectRunEventsOptions {
  baseUrl?: string;
  eventSourceFactory?: (url: string) => EventSource;
  onError?: (event: Event) => void;
}

export interface RunEventsClient {
  close: () => void;
}

const DEFAULT_BASE_URL = "/api";

export function connectRunEvents(
  runId: string,
  handlers: RunEventHandlers,
  options: ConnectRunEventsOptions = {},
): RunEventsClient {
  const baseUrl = options.baseUrl ?? DEFAULT_BASE_URL;
  const url = `${baseUrl}/runs/${runId}/events`;
  const factory =
    options.eventSourceFactory ?? ((source: string) => new EventSource(source));
  const source = factory(url);

  for (const type of RUN_EVENT_TYPES) {
    const handler = handlers[type];
    if (!handler) continue;
    source.addEventListener(type, (event) => {
      handler(JSON.parse((event as MessageEvent<string>).data));
    });
  }

  if (options.onError) {
    source.addEventListener("error", options.onError);
  }

  return {
    close: () => source.close(),
  };
}
