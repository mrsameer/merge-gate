// T018 — SSE EventSource client test for frontend/src/state/.
//
// contracts/control-plane-api.md's SSE section names the run-event stream's
// event types (node_status, harness_output, command_result, verdict, retry,
// gate, policy_block, terminal) with LedgerEntry-shaped JSON payloads. jsdom
// has no EventSource implementation, so the client accepts an injectable
// factory and this test exercises it against a fake EventSource.

import { describe, it, expect, vi } from "vitest";
import { connectRunEvents } from "../../src/state/sseClient";

class FakeEventSource {
  public url: string;
  public closed = false;
  private listeners = new Map<
    string,
    Array<(event: { data: string; lastEventId: string }) => void>
  >();

  constructor(url: string) {
    this.url = url;
  }

  addEventListener(
    type: string,
    listener: (event: { data: string; lastEventId: string }) => void,
  ) {
    const existing = this.listeners.get(type) ?? [];
    existing.push(listener);
    this.listeners.set(type, existing);
  }

  dispatch(type: string, payload: unknown, lastEventId = "") {
    for (const listener of this.listeners.get(type) ?? []) {
      listener({ data: JSON.stringify(payload), lastEventId });
    }
  }

  close() {
    this.closed = true;
  }
}

describe("connectRunEvents", () => {
  it("opens the run's event stream URL", () => {
    let created: FakeEventSource | undefined;
    connectRunEvents(
      "run-1",
      {},
      {
        eventSourceFactory: (url) => {
          created = new FakeEventSource(url);
          return created as unknown as EventSource;
        },
      },
    );

    expect(created?.url).toBe("/api/runs/run-1/events");
  });

  it("parses JSON payloads and routes them to the matching event handler", () => {
    let created: FakeEventSource | undefined;
    const onNodeStatus = vi.fn();
    const onVerdict = vi.fn();

    connectRunEvents(
      "run-1",
      { node_status: onNodeStatus, verdict: onVerdict },
      {
        eventSourceFactory: (url) => {
          created = new FakeEventSource(url);
          return created as unknown as EventSource;
        },
      },
    );

    created?.dispatch("node_status", {
      node_id: "n1",
      status: "running",
      attempt: 1,
    });
    expect(onNodeStatus).toHaveBeenCalledWith({
      node_id: "n1",
      status: "running",
      attempt: 1,
    });
    expect(onVerdict).not.toHaveBeenCalled();

    created?.dispatch("verdict", {
      attempt: 1,
      passed: true,
      acceptance_hash: "abc",
    });
    expect(onVerdict).toHaveBeenCalledWith({
      attempt: 1,
      passed: true,
      acceptance_hash: "abc",
    });
  });

  it("does not throw for event types with no registered handler", () => {
    let created: FakeEventSource | undefined;
    connectRunEvents(
      "run-2",
      { node_status: vi.fn() },
      {
        eventSourceFactory: (url) => {
          created = new FakeEventSource(url);
          return created as unknown as EventSource;
        },
      },
    );

    expect(() =>
      created?.dispatch("terminal", { state: "SUCCESS" }),
    ).not.toThrow();
  });

  it("closes the underlying EventSource on close()", () => {
    let created: FakeEventSource | undefined;
    const client = connectRunEvents(
      "run-1",
      {},
      {
        eventSourceFactory: (url) => {
          created = new FakeEventSource(url);
          return created as unknown as EventSource;
        },
      },
    );

    client.close();
    expect(created?.closed).toBe(true);
  });

  it("resumes a refreshed client after its persisted event cursor", () => {
    let created: FakeEventSource | undefined;
    const onEventId = vi.fn();
    const options = {
      lastEventId: 7,
      onEventId,
      eventSourceFactory: (url: string) => {
        created = new FakeEventSource(url);
        return created as unknown as EventSource;
      },
    };

    connectRunEvents("run-refresh", { retry: vi.fn() }, options);
    created?.dispatch("retry", { attempt: 2 }, "8");

    expect(created?.url).toBe("/api/runs/run-refresh/events?last_event_id=7");
    expect(onEventId).toHaveBeenCalledWith(8);
  });

  it("adds an event ticket for an authenticated stream", () => {
    let created: FakeEventSource | undefined;

    connectRunEvents(
      "private-run",
      {},
      {
        ticket: "short-lived-ticket",
        eventSourceFactory: (url) => {
          created = new FakeEventSource(url);
          return created as unknown as EventSource;
        },
      },
    );

    expect(created?.url).toBe(
      "/api/runs/private-run/events?ticket=short-lived-ticket",
    );
  });
});
