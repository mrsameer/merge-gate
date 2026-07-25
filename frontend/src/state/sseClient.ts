// SSE `EventSource` client for the run event stream, per
// specs/001-mergegate-control-plane/contracts/control-plane-api.md
// (`GET /runs/{id}/events`). Native EventSource resends `Last-Event-ID` while
// one page stays open. A full browser refresh creates a new EventSource, so
// the persisted cursor is also sent as a query fallback.

import { getApiBaseUrl } from "../api/client";

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
  lastEventId?: number | null;
  onEventId?: (eventId: number) => void;
  ticket?: string | null;
}

export interface RunEventsClient {
  close: () => void;
}

export function connectRunEvents(
  runId: string,
  handlers: RunEventHandlers,
  options: ConnectRunEventsOptions = {},
): RunEventsClient {
  const baseUrl = options.baseUrl ?? getApiBaseUrl();
  const eventUrl = `${baseUrl}/runs/${runId}/events`;
  const params = new URLSearchParams();
  if (options.lastEventId !== null && options.lastEventId !== undefined) {
    params.set("last_event_id", String(options.lastEventId));
  }
  if (options.ticket) params.set("ticket", options.ticket);
  const url = params.size ? `${eventUrl}?${params}` : eventUrl;
  const factory =
    options.eventSourceFactory ?? ((source: string) => new EventSource(source));
  const source = factory(url);

  for (const type of RUN_EVENT_TYPES) {
    const handler = handlers[type];
    if (!handler) continue;
    source.addEventListener(type, (event) => {
      const message = event as MessageEvent<string>;
      const eventId = Number(message.lastEventId);
      if (message.lastEventId && Number.isSafeInteger(eventId)) {
        options.onEventId?.(eventId);
      }
      handler(JSON.parse(message.data));
    });
  }

  if (options.onError) {
    source.addEventListener("error", options.onError);
  }

  return {
    close: () => source.close(),
  };
}
