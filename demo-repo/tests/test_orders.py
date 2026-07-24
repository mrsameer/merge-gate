from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_order_returns_created_status() -> None:
    response = client.post("/orders", json={"sku": "widget"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "created"
    assert body["sku"] == "widget"
