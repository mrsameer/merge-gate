"""Tests for the protected auth module guarding `app/orders`."""

ORDER_PAYLOAD = {"customer_id": "cust-1", "item": "widget", "quantity": 2}


def test_create_order_without_api_key_is_rejected(client) -> None:
    response = client.post("/orders", json=ORDER_PAYLOAD)

    assert response.status_code == 401


def test_create_order_with_wrong_api_key_is_rejected(client) -> None:
    response = client.post(
        "/orders", json=ORDER_PAYLOAD, headers={"X-API-Key": "wrong-key"}
    )

    assert response.status_code == 401


def test_create_order_with_valid_api_key_is_accepted(client, auth_headers) -> None:
    response = client.post("/orders", json=ORDER_PAYLOAD, headers=auth_headers)

    assert response.status_code == 201
