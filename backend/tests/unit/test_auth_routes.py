"""Authentication route tests without a live GitHub OAuth exchange."""

from __future__ import annotations

import importlib

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from mergegate.auth.store import AuthStore


def test_session_and_connection_routes_use_bearer_session(
    monkeypatch, tmp_path
) -> None:
    auth_router = importlib.import_module("mergegate.auth.router")
    store = AuthStore(
        data_dir=tmp_path,
        encryption_key=Fernet.generate_key().decode("utf-8"),
    )
    user = store.upsert_github_user(
        github_id="123",
        login="mergegate-user",
        avatar_url=None,
        access_token="github-secret",
    )
    token = store.create_session(user.id)
    monkeypatch.setattr(auth_router, "get_auth_store", lambda: store)

    from mergegate.api.main import app

    client = TestClient(app)
    unauthenticated = client.get("/api/auth/session")
    authenticated = client.get(
        "/api/auth/session", headers={"Authorization": f"Bearer {token}"}
    )
    saved = client.put(
        "/api/auth/connections/gemini_api_key",
        json={"secret": "gemini-secret", "label": "Gemini"},
        headers={"Authorization": f"Bearer {token}"},
    )
    connections = client.get(
        "/api/auth/connections", headers={"Authorization": f"Bearer {token}"}
    )

    assert unauthenticated.json() == {"authenticated": False}
    assert authenticated.json()["user"]["github_login"] == "mergegate-user"
    assert saved.status_code == 204
    assert {connection["kind"] for connection in connections.json()} == {
        "gemini_api_key",
        "github_oauth",
    }
    assert "gemini-secret" not in connections.text
