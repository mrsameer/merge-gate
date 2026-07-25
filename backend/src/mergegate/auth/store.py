"""Encrypted, local persistence for user sessions and provider connections."""

from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from mergegate.acceptance.commands import run_command

_SESSION_TTL = timedelta(days=7)
_OAUTH_STATE_TTL = timedelta(minutes=10)
_EVENT_TICKET_TTL = timedelta(minutes=2)
_CONNECTION_KINDS = frozenset(
    {"github_oauth", "github_pat", "gemini_api_key", "claude_oauth_token"}
)


class AuthConfigurationError(RuntimeError):
    """Raised when a production-only auth secret has not been configured."""


class AuthenticationError(RuntimeError):
    """Raised for missing, expired, or malformed sessions."""


class ConnectionError(RuntimeError):
    """Raised when a requested credential connection is unavailable."""


@dataclass(frozen=True)
class CurrentUser:
    id: str
    github_login: str
    avatar_url: str | None = None


@dataclass(frozen=True)
class ConnectionSummary:
    kind: str
    label: str
    updated_at: str


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _timestamp(value: datetime) -> str:
    return value.isoformat()


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _default_data_dir() -> Path:
    configured = os.environ.get("MERGEGATE_DATA_DIR")
    if configured:
        return Path(configured)
    return Path(tempfile.gettempdir()) / "mergegate-data"


class AuthStore:
    """SQLite-backed account data with Fernet-encrypted connection secrets."""

    def __init__(self, data_dir: Path | None = None, encryption_key: str | None = None):
        self._data_dir = data_dir or _default_data_dir()
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = self._data_dir / "auth.sqlite3"
        key = encryption_key or os.environ.get("MERGEGATE_CREDENTIAL_ENCRYPTION_KEY")
        self._cipher = self._load_cipher(key)
        self._init_schema()

    @staticmethod
    def _load_cipher(key: str | None) -> Fernet | None:
        if not key:
            return None
        try:
            return Fernet(key.encode("utf-8"))
        except (TypeError, ValueError) as exc:
            raise AuthConfigurationError(
                "MERGEGATE_CREDENTIAL_ENCRYPTION_KEY must be a Fernet key"
            ) from exc

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    github_id TEXT UNIQUE NOT NULL,
                    github_login TEXT NOT NULL,
                    avatar_url TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    expires_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS oauth_states (
                    state_hash TEXT PRIMARY KEY,
                    return_to TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS event_tickets (
                    ticket_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    run_id TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS connections (
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    kind TEXT NOT NULL,
                    label TEXT NOT NULL,
                    ciphertext BLOB NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, kind)
                );
                CREATE TABLE IF NOT EXISTS repositories (
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    full_name TEXT NOT NULL,
                    clone_path TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, full_name)
                );
                """
            )

    def _encrypt(self, secret: str) -> bytes:
        if self._cipher is None:
            raise AuthConfigurationError(
                "Credential storage is disabled; set "
                "MERGEGATE_CREDENTIAL_ENCRYPTION_KEY first"
            )
        return self._cipher.encrypt(secret.encode("utf-8"))

    def require_credential_storage(self) -> None:
        """Fail closed before an OAuth callback tries to save a credential."""
        if self._cipher is None:
            raise AuthConfigurationError(
                "Credential storage is disabled; set "
                "MERGEGATE_CREDENTIAL_ENCRYPTION_KEY first"
            )

    def _decrypt(self, ciphertext: bytes) -> str:
        if self._cipher is None:
            raise AuthConfigurationError("Credential storage is not configured")
        try:
            return self._cipher.decrypt(ciphertext).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError) as exc:
            raise ConnectionError("Stored credential cannot be decrypted") from exc

    def create_oauth_state(self, return_to: str) -> str:
        state = secrets.token_urlsafe(32)
        expires = _timestamp(_utc_now() + _OAUTH_STATE_TTL)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO oauth_states "
                "(state_hash, return_to, expires_at) VALUES (?, ?, ?)",
                (_digest(state), return_to, expires),
            )
        return state

    def consume_oauth_state(self, state: str) -> str:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT return_to, expires_at FROM oauth_states WHERE state_hash = ?",
                (_digest(state),),
            ).fetchone()
            conn.execute(
                "DELETE FROM oauth_states WHERE state_hash = ?", (_digest(state),)
            )
        if row is None or datetime.fromisoformat(row["expires_at"]) <= _utc_now():
            raise AuthenticationError("GitHub sign-in state is invalid or expired")
        return str(row["return_to"])

    def upsert_github_user(
        self, *, github_id: str, login: str, avatar_url: str | None, access_token: str
    ) -> CurrentUser:
        now = _timestamp(_utc_now())
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM users WHERE github_id = ?", (github_id,)
            ).fetchone()
            user_id = str(row["id"]) if row else secrets.token_urlsafe(18)
            if row:
                conn.execute(
                    "UPDATE users SET github_login = ?, avatar_url = ?, updated_at = ? "
                    "WHERE id = ?",
                    (login, avatar_url, now, user_id),
                )
            else:
                conn.execute(
                    "INSERT INTO users (id, github_id, github_login, avatar_url, "
                    "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (user_id, github_id, login, avatar_url, now, now),
                )
        self.put_connection(user_id, "github_oauth", access_token, "GitHub OAuth")
        return CurrentUser(id=user_id, github_login=login, avatar_url=avatar_url)

    def create_session(self, user_id: str) -> str:
        token = secrets.token_urlsafe(40)
        expires = _timestamp(_utc_now() + _SESSION_TTL)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO sessions "
                "(token_hash, user_id, expires_at) VALUES (?, ?, ?)",
                (_digest(token), user_id, expires),
            )
        return token

    def current_user(self, token: str | None) -> CurrentUser | None:
        if not token:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT users.id, users.github_login, users.avatar_url, "
                "sessions.expires_at "
                "FROM sessions JOIN users ON users.id = sessions.user_id "
                "WHERE sessions.token_hash = ?",
                (_digest(token),),
            ).fetchone()
            if (
                row is not None
                and datetime.fromisoformat(row["expires_at"]) <= _utc_now()
            ):
                conn.execute(
                    "DELETE FROM sessions WHERE token_hash = ?", (_digest(token),)
                )
                row = None
        if row is None:
            return None
        return CurrentUser(
            id=str(row["id"]),
            github_login=str(row["github_login"]),
            avatar_url=row["avatar_url"],
        )

    def revoke_session(self, token: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_digest(token),))

    def create_event_ticket(self, user_id: str, run_id: str) -> str:
        ticket = secrets.token_urlsafe(24)
        expires_at = _timestamp(_utc_now() + _EVENT_TICKET_TTL)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO event_tickets "
                "(ticket_hash, user_id, run_id, expires_at) VALUES (?, ?, ?, ?)",
                (_digest(ticket), user_id, run_id, expires_at),
            )
        return ticket

    def consume_event_ticket(self, ticket: str, run_id: str) -> str | None:
        ticket_hash = _digest(ticket)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT user_id, expires_at FROM event_tickets "
                "WHERE ticket_hash = ? AND run_id = ?",
                (ticket_hash, run_id),
            ).fetchone()
        if row is None or datetime.fromisoformat(row["expires_at"]) <= _utc_now():
            with self._connect() as conn:
                conn.execute(
                    "DELETE FROM event_tickets WHERE ticket_hash = ?", (ticket_hash,)
                )
            return None
        return str(row["user_id"])

    def put_connection(self, user_id: str, kind: str, secret: str, label: str) -> None:
        if kind not in _CONNECTION_KINDS:
            raise ConnectionError(f"Unsupported credential connection: {kind}")
        if not secret.strip():
            raise ConnectionError("Credential value cannot be empty")
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO connections "
                "(user_id, kind, label, ciphertext, updated_at) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT(user_id, kind) DO UPDATE SET "
                "label = excluded.label, ciphertext = excluded.ciphertext, "
                "updated_at = excluded.updated_at",
                (
                    user_id,
                    kind,
                    label.strip() or kind,
                    self._encrypt(secret),
                    _timestamp(_utc_now()),
                ),
            )

    def delete_connection(self, user_id: str, kind: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM connections WHERE user_id = ? AND kind = ?",
                (user_id, kind),
            )

    def list_connections(self, user_id: str) -> list[ConnectionSummary]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT kind, label, updated_at FROM connections WHERE user_id = ? "
                "ORDER BY kind",
                (user_id,),
            ).fetchall()
        return [
            ConnectionSummary(
                kind=str(row["kind"]),
                label=str(row["label"]),
                updated_at=str(row["updated_at"]),
            )
            for row in rows
        ]

    def get_connection_secret(self, user_id: str, kind: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT ciphertext FROM connections WHERE user_id = ? AND kind = ?",
                (user_id, kind),
            ).fetchone()
        return self._decrypt(row["ciphertext"]) if row else None

    def provider_secret(self, user_id: str, provider: str) -> str | None:
        kind = {
            "gemini": "gemini_api_key",
            "anthropic": "claude_oauth_token",
            "claude-agent-sdk": "claude_oauth_token",
        }.get(provider)
        return self.get_connection_secret(user_id, kind) if kind else None

    def github_token(self, user_id: str) -> str | None:
        return self.get_connection_secret(
            user_id, "github_pat"
        ) or self.get_connection_secret(user_id, "github_oauth")

    def clone_repository(self, user_id: str, full_name: str) -> Path:
        if not full_name or full_name.count("/") != 1:
            raise ConnectionError("Repository must use the owner/repository format")
        owner, name = full_name.split("/", 1)
        normalized = (
            part.replace("-", "").replace("_", "").replace(".", "")
            for part in (owner, name)
        )
        if not all(part.isalnum() for part in normalized):
            raise ConnectionError("Repository contains unsupported characters")
        token = self.github_token(user_id)
        if not token:
            raise ConnectionError(
                "Connect GitHub or save a GitHub PAT before selecting a repository"
            )
        target = self._data_dir / "repositories" / user_id / owner / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_dir() and (target / ".git").is_dir():
            return target
        askpass = self._data_dir / f"git-askpass-{secrets.token_hex(8)}.sh"
        askpass.write_text(
            '#!/bin/sh\nprintf "%s\\n" "$MERGEGATE_GIT_TOKEN"\n', encoding="utf-8"
        )
        askpass.chmod(0o700)
        try:
            result = run_command(
                [
                    "git",
                    "clone",
                    "--depth",
                    "1",
                    f"https://github.com/{owner}/{name}.git",
                    str(target),
                ],
                extra_env={
                    "GIT_ASKPASS": str(askpass),
                    "GIT_TERMINAL_PROMPT": "0",
                    "MERGEGATE_GIT_TOKEN": token,
                },
                timeout_s=180,
            )
        finally:
            askpass.unlink(missing_ok=True)
        if not result.succeeded:
            raise ConnectionError(
                f"Could not clone {full_name}; verify repository access"
            )
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO repositories (user_id, full_name, clone_path, updated_at) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(user_id, full_name) DO UPDATE SET "
                "clone_path = excluded.clone_path, updated_at = excluded.updated_at",
                (user_id, full_name, str(target), _timestamp(_utc_now())),
            )
        return target


_AUTH_STORE: AuthStore | None = None


def get_auth_store() -> AuthStore:
    global _AUTH_STORE
    if _AUTH_STORE is None:
        _AUTH_STORE = AuthStore()
    return _AUTH_STORE
