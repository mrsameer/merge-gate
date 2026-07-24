"""T010 unit tests: FastAPI app skeleton, router wiring, and error envelope.

Encodes the acceptance criteria for `backend/src/mergegate/api/main.py`: an
importable `FastAPI` app, an `/api`-mounted router wired end-to-end, and the
uniform `{"error": {"code", "message"}}` envelope required by
`specs/001-mergegate-control-plane/contracts/control-plane-api.md`.

Written FIRST and MUST FAIL (ModuleNotFoundError) until T010 lands.
"""

from __future__ import annotations

import json

import anyio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request


def _request(path: str = "/api/example") -> Request:
    return Request({"type": "http", "method": "GET", "path": path, "headers": []})


def test_app_is_a_fastapi_instance() -> None:
    from mergegate.api.main import app

    assert isinstance(app, FastAPI)


def test_health_endpoint_confirms_router_wiring() -> None:
    from mergegate.api.main import app

    client = TestClient(app)
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unmatched_route_returns_error_envelope() -> None:
    from mergegate.api.main import app

    client = TestClient(app)
    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    body = response.json()
    assert set(body["error"]) >= {"code", "message"}
    assert body["error"]["code"] == "NOT_FOUND"


def test_http_exception_handler_preserves_status_and_detail() -> None:
    from mergegate.api.main import handle_http_exception

    exc = StarletteHTTPException(status_code=409, detail="conflict for testing")
    response = anyio.run(handle_http_exception, _request(), exc)

    assert response.status_code == 409
    body = json.loads(bytes(response.body))
    assert body == {"error": {"code": "CONFLICT", "message": "conflict for testing"}}


def test_unexpected_exception_handler_returns_500_envelope() -> None:
    from mergegate.api.main import handle_unexpected_error

    response = anyio.run(handle_unexpected_error, _request(), RuntimeError("boom"))

    assert response.status_code == 500
    body = json.loads(bytes(response.body))
    assert body["error"]["code"] == "INTERNAL_ERROR"
