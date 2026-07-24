"""T011 unit tests: SSE event stream endpoint + in-process event bus.

Encodes the acceptance criteria for `backend/src/mergegate/api/events.py`: a
per-run pub/sub bus that buffers events for replay, and a `/runs/{id}/events`
SSE endpoint that supports `Last-Event-ID` reconnect (the mid-run client
refresh edge case in spec.md, SC-011).

Written FIRST and MUST FAIL (ModuleNotFoundError) until T011 lands.
"""

from __future__ import annotations

import json
from typing import cast

import anyio
from starlette.requests import Request


def test_publish_assigns_monotonic_per_run_sequence() -> None:
    from mergegate.api.events import EventBus

    bus = EventBus()
    first = bus.publish(
        "run-1", "node_status", {"node_id": "planning", "status": "running"}
    )
    second = bus.publish(
        "run-1", "node_status", {"node_id": "planning", "status": "done"}
    )
    other_run = bus.publish("run-2", "gate", {"kind": "contract", "state": "awaiting"})

    assert (first.seq, second.seq) == (1, 2)
    assert other_run.seq == 1


def test_subscribe_replays_buffered_events_after_last_event_id() -> None:
    from mergegate.api.events import EventBus

    async def scenario() -> list[int]:
        bus = EventBus()
        bus.publish("run-1", "node_status", {"node_id": "planning", "status": "run"})
        bus.publish("run-1", "node_status", {"node_id": "planning", "status": "done"})
        bus.publish(
            "run-1", "verdict", {"attempt": 1, "passed": True, "acceptance_hash": "a"}
        )

        seen = []
        async for event in bus.subscribe("run-1", last_event_id=1):
            seen.append(event.seq)
            if len(seen) == 2:
                break
        return seen

    assert anyio.run(scenario) == [2, 3]


def test_subscribe_streams_new_events_published_after_subscription() -> None:
    from mergegate.api.events import EventBus

    async def scenario() -> int:
        bus = EventBus()
        seen: list[int] = []

        async def publisher() -> None:
            await anyio.sleep(0.01)
            bus.publish("run-1", "terminal", {"state": "success"})

        async with anyio.create_task_group() as tg:
            tg.start_soon(publisher)
            async for event in bus.subscribe("run-1"):
                seen.append(event.seq)
                break
        return seen[0]

    assert anyio.run(scenario) == 1


def _request(path: str, last_event_id: str | None = None) -> Request:
    """A minimal ASGI request whose `receive()` never reports a disconnect.

    The endpoint is exercised directly (rather than through an HTTP test
    client) because `httpx.ASGITransport` runs the whole ASGI call to
    completion before returning a response, which can never work for a
    stream that only ends when the client disconnects.
    """
    headers = [(b"last-event-id", last_event_id.encode())] if last_event_id else []

    async def receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(
        {"type": "http", "method": "GET", "path": path, "headers": headers}, receive
    )


def test_stream_endpoint_yields_buffered_event_as_sse_payload() -> None:
    from mergegate.api.events import event_bus, stream_run_events

    run_id = "run-endpoint-test"
    event_bus.publish(
        run_id, "node_status", {"node_id": "planning", "status": "running"}
    )

    async def scenario() -> dict:
        response = await stream_run_events(run_id, _request(f"/runs/{run_id}/events"))
        assert response.media_type == "text/event-stream"
        return cast(dict, await anext(aiter(response.body_iterator)))

    item = anyio.run(scenario)
    assert item == {
        "id": "1",
        "event": "node_status",
        "data": json.dumps({"node_id": "planning", "status": "running"}),
    }


def test_stream_endpoint_reconnect_replays_only_events_after_last_event_id() -> None:
    from mergegate.api.events import event_bus, stream_run_events

    run_id = "run-reconnect-test"
    event_bus.publish(run_id, "node_status", {"node_id": "planning", "status": "run"})
    event_bus.publish(run_id, "node_status", {"node_id": "planning", "status": "done"})

    async def scenario() -> dict:
        request = _request(f"/runs/{run_id}/events", last_event_id="1")
        response = await stream_run_events(run_id, request)
        return cast(dict, await anext(aiter(response.body_iterator)))

    item = anyio.run(scenario)
    assert item["id"] == "2"


def test_events_router_is_wired_into_app() -> None:
    from mergegate.api.main import app

    assert app.url_path_for("stream_run_events", run_id="abc") == "/api/runs/abc/events"
