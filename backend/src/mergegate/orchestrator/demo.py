"""Deterministic demo scenario for the US1 happy-path loop (no API key needed).

The integration tests create runs against the bundled ``demo-repo`` FastAPI
order service and expect the loop to reach a passing verdict without any live
provider. This module supplies the two deterministic pieces that make that
possible:

* :func:`demo_idempotency_changes` — the file set a ``scripted`` harness writes
  into the attempt worktree to satisfy the "make ``POST /orders`` idempotent"
  objective. It adds an idempotency cache to ``store.py`` and the
  ``Idempotency-Key`` header handling to ``router.py``, plus a new test file,
  and deliberately never touches ``app/auth`` (the protected module).
* :func:`is_demo_repo` — recognises the demo-repo objective/repo so the API can
  default such runs to the ``scripted`` provider in environments with no key.

Everything here is plain data (file contents keyed by repo-relative path); the
acceptance decision is still computed by the separate engine over real command
exit codes, never asserted here.
"""

from __future__ import annotations

_STORE_PY = '''\
"""In-memory order storage with idempotent creation support."""

import hashlib
import json
from uuid import uuid4

from app.orders.models import Order, OrderCreate

_orders: dict[str, Order] = {}
_idempotency: dict[str, tuple[str, Order]] = {}


class IdempotencyConflict(Exception):
    """Raised when an Idempotency-Key is reused with a different request body."""


def _body_fingerprint(payload: OrderCreate) -> str:
    canonical = json.dumps(
        payload.model_dump(), sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def create_order(payload: OrderCreate, idempotency_key: str | None = None) -> Order:
    if idempotency_key is not None:
        fingerprint = _body_fingerprint(payload)
        existing = _idempotency.get(idempotency_key)
        if existing is not None:
            stored_fingerprint, stored_order = existing
            if stored_fingerprint != fingerprint:
                raise IdempotencyConflict(idempotency_key)
            return stored_order

    order = Order(id=str(uuid4()), **payload.model_dump())
    _orders[order.id] = order
    if idempotency_key is not None:
        _idempotency[idempotency_key] = (_body_fingerprint(payload), order)
    return order
'''

_ROUTER_PY = '''\
"""`POST /orders` — idempotent order creation (the seed objective)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.auth.security import require_api_key
from app.orders.models import Order, OrderCreate
from app.orders.store import IdempotencyConflict, create_order

router = APIRouter(
    prefix="/orders",
    tags=["orders"],
    dependencies=[Depends(require_api_key)],
)


@router.post("", response_model=Order, status_code=status.HTTP_201_CREATED)
def post_order(
    payload: OrderCreate,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> Order:
    """Create an order, reusing the original when the Idempotency-Key repeats."""
    try:
        return create_order(payload, idempotency_key=idempotency_key)
    except IdempotencyConflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency-Key reused with a different request body",
        ) from None
'''

_TEST_IDEMPOTENCY_PY = '''\
"""Idempotency behaviour for POST /orders (the seed objective)."""

from app.auth.security import API_KEY

PAYLOAD = {"customer_id": "cust-1", "item": "widget", "quantity": 2}
HEADERS = {"X-API-Key": API_KEY}


def test_same_key_same_body_returns_original_order(client) -> None:
    key = {"Idempotency-Key": "abc-123"}
    first = client.post("/orders", json=PAYLOAD, headers={**HEADERS, **key})
    second = client.post("/orders", json=PAYLOAD, headers={**HEADERS, **key})
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]


def test_same_key_different_body_returns_409(client) -> None:
    key = {"Idempotency-Key": "conflict-1"}
    first = client.post("/orders", json=PAYLOAD, headers={**HEADERS, **key})
    other = {**PAYLOAD, "quantity": 99}
    second = client.post("/orders", json=other, headers={**HEADERS, **key})
    assert first.status_code == 201
    assert second.status_code == 409


def test_missing_key_creates_separate_orders(client) -> None:
    first = client.post("/orders", json=PAYLOAD, headers=HEADERS)
    second = client.post("/orders", json=PAYLOAD, headers=HEADERS)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
'''


def demo_idempotency_changes(prefix: str = "") -> dict[str, str]:
    """Return worktree-relative path -> new contents for the idempotency task.

    ``prefix`` is prepended to every path so the change set can be written into
    a worktree where the demo repo lives in a subdirectory (e.g. ``demo-repo``
    inside a mono-repo checkout). It never includes anything under ``app/auth``.
    """
    base = f"{prefix.rstrip('/')}/" if prefix.strip("/") else ""
    return {
        f"{base}app/orders/store.py": _STORE_PY,
        f"{base}app/orders/router.py": _ROUTER_PY,
        f"{base}tests/test_idempotency.py": _TEST_IDEMPOTENCY_PY,
    }


def is_demo_repo(repo_ref: str, objective: str) -> bool:
    """Whether this run targets the bundled demo-repo idempotency scenario."""
    return "demo-repo" in repo_ref and "idempot" in objective.lower()
