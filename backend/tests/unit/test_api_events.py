"""T011 unit tests: SSE event stream endpoint + in-process event bus.

Encodes the acceptance criteria for `backend/src/mergegate/api/events.py`: a
per-run pub/sub bus that buffers events for replay, and a `/runs/{id}/events`
SSE endpoint that supports `Last-Event-ID` reconnect (the mid-run client
refresh edge case in spec.md, SC-011).

Written FIRST and MUST FAIL (ModuleNotFoundError) until T011 lands.
"""

from __future__ import annotations

import anyio
import httpx


def test_publish_assigns_monotonic_per_run_sequence() -> None:
    from mergegate.api.events import EventBus

    bus = EventBus()
    first = bus.publish(
        "run-1", "node_status", {"node_id": "planning", "status": "running"}
    )
    second = bus.publish(
        "run-1", "node_status", {"node_id": "planning", "status": "done"}
    )
    other_run = bus.publish(
        "run-2", "gate", {"kind": "contract", "state": "awaiting"}
    )

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


def test_stream_endpoint_emits_buffered_event_with_last_event_id() -> None:
    from mergegate.api.events import event_bus
    from mergegate.api.main import app

    run_id = "run-endpoint-test"
    event_bus.publish(
        run_id, "node_status", {"node_id": "planning", "status": "running"}
    )

    async def scenario() -> list[str]:
        transport = httpx.ASGITransport(app=app)
        lines: list[str] = []
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            async with client.stream("GET", f"/api/runs/{run_id}/events") as response:
                assert response.status_code == 200
                assert response.headers["content-type"].startswith(
                    "text/event-stream"
                )
                async for line in response.aiter_lines():
                    lines.append(line)
                    if line.startswith("data:"):
                        break
        return lines

    lines = anyio.run(scenario)
    assert "event: node_status" in lines
    assert "id: 1" in lines
    assert (
        'data: {"node_id": "planning", "status": "running"}' in lines
    )


def test_stream_endpoint_reconnect_replays_only_events_after_last_event_id() -> None:
    from mergegate.api.events import event_bus
    from mergegate.api.main import app

    run_id = "run-reconnect-test"
    event_bus.publish(run_id, "node_status", {"node_id": "planning", "status": "run"})
    event_bus.publish(run_id, "node_status", {"node_id": "planning", "status": "done"})

    async def scenario() -> list[str]:
        transport = httpx.ASGITransport(app=app)
        lines: list[str] = []
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            async with client.stream(
                "GET",
                f"/api/runs/{run_id}/events",
                headers={"Last-Event-ID": "1"},
            ) as response:
                async for line in response.aiter_lines():
                    lines.append(line)
                    if line.startswith("data:"):
                        break
        return lines

    lines = anyio.run(scenario)
    assert "id: 2" in lines
    assert "id: 1" not in lines
