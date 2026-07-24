"""SSE event stream — in-process bus placeholder for US1."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/runs/{run_id}/events")
def stream_events(run_id: str) -> dict:
    return {"run_id": run_id, "events": []}
