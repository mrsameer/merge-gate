"""`POST /orders` — the seed-task target endpoint."""

from fastapi import APIRouter, Depends, status

from app.auth.security import require_api_key
from app.orders.models import Order, OrderCreate
from app.orders.store import create_order

router = APIRouter(
    prefix="/orders",
    tags=["orders"],
    dependencies=[Depends(require_api_key)],
)


@router.post("", response_model=Order, status_code=status.HTTP_201_CREATED)
def post_order(payload: OrderCreate) -> Order:
    return create_order(payload)
