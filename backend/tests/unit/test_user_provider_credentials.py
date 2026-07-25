"""A connected user's provider credential must win over process environment."""

from __future__ import annotations

from cryptography.fernet import Fernet

from mergegate.auth.router import optional_current_user
from mergegate.auth.store import AuthStore


def test_owned_gemini_run_receives_vault_key(
    approved_run_id, app, client, monkeypatch, tmp_path
) -> None:
    from mergegate.api import runs
    from mergegate.api.store import store

    auth_store = AuthStore(
        data_dir=tmp_path,
        encryption_key=Fernet.generate_key().decode("utf-8"),
    )
    user = auth_store.upsert_github_user(
        github_id="123",
        login="mergegate-user",
        avatar_url=None,
        access_token="github-secret",
    )
    auth_store.put_connection(
        user.id,
        "gemini_api_key",
        "user-gemini-key",
        "Gemini",
    )
    record = store.get_run(approved_run_id)
    assert record is not None
    record.owner_id = user.id
    record.run.provider = "gemini"
    captured: dict[str, object] = {}

    def capture_context(context) -> None:
        captured.update(context.adapter_kwargs)

    monkeypatch.setattr(runs, "get_auth_store", lambda: auth_store)
    monkeypatch.setattr(runs, "drive_run", capture_context)
    app.dependency_overrides[optional_current_user] = lambda: user
    try:
        started = client.post(f"/api/runs/{approved_run_id}:start")
    finally:
        app.dependency_overrides.pop(optional_current_user, None)

    assert started.status_code == 202
    assert captured["api_key"] == "user-gemini-key"
    assert captured["location"] == "global"
