"""In-memory order storage.

Baseline behaviour only: every call creates a new order. Idempotent creation
(the `Idempotency-Key` seed objective) is intentionally not implemented here —
it is the target task for the loop to add on top of this fixture.
"""

from uuid import uuid4

from app.orders.models import Order, OrderCreate

_orders: dict[str, Order] = {}


def create_order(payload: OrderCreate) -> Order:
    order = Order(id=str(uuid4()), **payload.model_dump())
    _orders[order.id] = order
    return order
