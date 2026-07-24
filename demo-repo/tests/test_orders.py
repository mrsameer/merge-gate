"""Baseline tests for `POST /orders`.

This is the seed-task fixture (research.md R11): the loop's target objective is
adding idempotency to this endpoint later. These tests only cover the current,
deliberately non-idempotent baseline — a genuine starting point for that task.
"""

ORDER_PAYLOAD = {"customer_id": "cust-1", "item": "widget", "quantity": 2}


def test_create_order_returns_201_with_created_order(client, auth_headers) -> None:
    response = client.post("/orders", json=ORDER_PAYLOAD, headers=auth_headers)

    assert response.status_code == 201
    body = response.json()
    assert body["customer_id"] == ORDER_PAYLOAD["customer_id"]
    assert body["item"] == ORDER_PAYLOAD["item"]
    assert body["quantity"] == ORDER_PAYLOAD["quantity"]
    assert "id" in body


def test_repeated_identical_requests_currently_create_separate_orders(
    client, auth_headers
) -> None:
    """Documents the pre-idempotency baseline: no `Idempotency-Key` support yet."""
    first = client.post("/orders", json=ORDER_PAYLOAD, headers=auth_headers)
    second = client.post("/orders", json=ORDER_PAYLOAD, headers=auth_headers)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
