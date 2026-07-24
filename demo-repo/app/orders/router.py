from fastapi import APIRouter

router = APIRouter()


@router.post("")
def create_order(payload: dict) -> dict:
    """Baseline stub — idempotency is added by the MergeGate loop under test."""
    return {"id": "order-1", "status": "created", **payload}
