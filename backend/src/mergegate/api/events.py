"""In-process SSE event bus and `/runs/{id}/events` stream endpoint.

Each published event is buffered per `run_id` so a reconnecting client can
replay everything after its `Last-Event-ID` header (the mid-run browser
refresh edge case, `spec.md` SC-011) before switching to live delivery. Event
payloads follow the shapes named in
`specs/001-mergegate-control-plane/contracts/control-plane-api.md`
(`node_status`, `harness_output`, `command_result`, `verdict`, `retry`,
`gate`, `policy_block`, `terminal`).
"""

from __future__ import annotations

import json
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from dataclasses import dataclass

import anyio
from anyio.streams.memory import MemoryObjectSendStream
from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from mergegate.api.store import store
from mergegate.auth.store import get_auth_store

_REPLAY_BUFFER_SIZE = 1000


@dataclass(frozen=True)
class Event:
    """A single published event, ordered by `seq` within its `run_id`."""

    seq: int
    run_id: str
    event_type: str
    payload: dict


class EventBus:
    """Per-run in-process pub/sub with a bounded replay buffer."""

    def __init__(self, buffer_size: int = _REPLAY_BUFFER_SIZE) -> None:
        self._buffer_size = buffer_size
        self._next_seq: dict[str, int] = defaultdict(int)
        self._buffers: dict[str, deque[Event]] = defaultdict(
            lambda: deque(maxlen=buffer_size)
        )
        self._subscribers: dict[str, set[MemoryObjectSendStream[Event]]] = defaultdict(
            set
        )

    def publish(self, run_id: str, event_type: str, payload: dict) -> Event:
        """Record an event for `run_id` and fan it out to live subscribers."""
        self._next_seq[run_id] += 1
        event = Event(
            seq=self._next_seq[run_id],
            run_id=run_id,
            event_type=event_type,
            payload=payload,
        )
        self._buffers[run_id].append(event)
        for sender in list(self._subscribers[run_id]):
            sender.send_nowait(event)
        return event

    async def subscribe(
        self, run_id: str, last_event_id: int | None = None
    ) -> AsyncIterator[Event]:
        """Yield buffered events after `last_event_id`, then stream live ones."""
        send_stream, receive_stream = anyio.create_memory_object_stream[Event](
            max_buffer_size=self._buffer_size
        )
        self._subscribers[run_id].add(send_stream)
        try:
            for event in list(self._buffers[run_id]):
                if last_event_id is None or event.seq > last_event_id:
                    yield event
            async for event in receive_stream:
                yield event
        finally:
            self._subscribers[run_id].discard(send_stream)
            await send_stream.aclose()


event_bus = EventBus()

router = APIRouter()


@router.get("/runs/{run_id}/events")
async def stream_run_events(run_id: str, request: Request) -> EventSourceResponse:
    """SSE stream of a run's events, reconnectable via `Last-Event-ID`."""
    record = store.get_run(run_id)
    if record is not None and record.owner_id is not None:
        ticket = request.query_params.get("ticket")
        ticket_owner = (
            get_auth_store().consume_event_ticket(ticket, run_id) if ticket else None
        )
        if ticket_owner != record.owner_id:
            raise HTTPException(status_code=404, detail=f"run {run_id!r} not found")
    query_last_event_id = (
        request.query_params.get("last_event_id")
        if "query_string" in request.scope
        else None
    )
    raw_last_event_id = request.headers.get("last-event-id") or query_last_event_id
    try:
        last_event_id = int(raw_last_event_id) if raw_last_event_id else None
    except ValueError:
        last_event_id = None

    async def event_generator() -> AsyncIterator[dict]:
        async for event in event_bus.subscribe(run_id, last_event_id):
            if await request.is_disconnected():
                break
            yield {
                "id": str(event.seq),
                "event": event.event_type,
                "data": json.dumps(event.payload),
            }

    return EventSourceResponse(event_generator())
