"""Security tests for encrypted connections and opaque user sessions."""

from __future__ import annotations

import sqlite3

import pytest
from cryptography.fernet import Fernet

from mergegate.auth.store import AuthenticationError, AuthStore


@pytest.fixture()
def auth_store(tmp_path):
    return AuthStore(
        data_dir=tmp_path,
        encryption_key=Fernet.generate_key().decode("utf-8"),
    )


def test_connections_are_encrypted_and_never_returned_by_list(
    auth_store, tmp_path
) -> None:
    user = auth_store.upsert_github_user(
        github_id="123",
        login="mergegate-user",
        avatar_url=None,
        access_token="github-secret",
    )
    auth_store.put_connection(
        user.id,
        "gemini_api_key",
        "gemini-secret",
        "Personal Gemini key",
    )

    assert auth_store.provider_secret(user.id, "gemini") == "gemini-secret"
    assert [connection.kind for connection in auth_store.list_connections(user.id)] == [
        "gemini_api_key",
        "github_oauth",
    ]
    with sqlite3.connect(tmp_path / "auth.sqlite3") as conn:
        ciphertext = conn.execute(
            "SELECT ciphertext FROM connections WHERE kind = 'gemini_api_key'"
        ).fetchone()[0]
    assert b"gemini-secret" not in ciphertext


def test_sessions_are_opaque_and_can_be_revoked(auth_store) -> None:
    user = auth_store.upsert_github_user(
        github_id="123",
        login="mergegate-user",
        avatar_url="https://example.test/avatar.png",
        access_token="github-secret",
    )
    token = auth_store.create_session(user.id)

    assert auth_store.current_user(token) == user
    auth_store.revoke_session(token)
    assert auth_store.current_user(token) is None


def test_oauth_state_is_single_use(auth_store) -> None:
    state = auth_store.create_oauth_state("https://app.example.test")

    assert auth_store.consume_oauth_state(state) == "https://app.example.test"
    with pytest.raises(AuthenticationError):
        auth_store.consume_oauth_state(state)


def test_event_ticket_only_authorizes_its_owner_and_run(auth_store) -> None:
    user = auth_store.upsert_github_user(
        github_id="123",
        login="mergegate-user",
        avatar_url=None,
        access_token="github-secret",
    )
    ticket = auth_store.create_event_ticket(user.id, "run-1")

    assert auth_store.consume_event_ticket(ticket, "run-1") == user.id
    assert auth_store.consume_event_ticket(ticket, "run-1") == user.id

    wrong_run_ticket = auth_store.create_event_ticket(user.id, "run-1")
    assert auth_store.consume_event_ticket(wrong_run_ticket, "run-2") is None
