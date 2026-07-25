"""GitHub OAuth and authenticated server-side credential connections."""

from __future__ import annotations

import json
import os
from typing import Annotated
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from mergegate.auth.store import (
    AuthConfigurationError,
    AuthStore,
    ConnectionError,
    CurrentUser,
    get_auth_store,
)
from mergegate.config.settings import load_cors_allow_origins

router = APIRouter(prefix="/auth", tags=["auth"])

_GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
_GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
_GITHUB_USER_URL = "https://api.github.com/user"


class ConnectionRequest(BaseModel):
    secret: str = Field(min_length=1, max_length=16_384)
    label: str = Field(default="", max_length=120)


class RepositoryRequest(BaseModel):
    full_name: str = Field(min_length=3, max_length=200)


def _store() -> AuthStore:
    return get_auth_store()


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return authorization.removeprefix("Bearer ").strip() or None


def optional_current_user(
    authorization: Annotated[str | None, Header()] = None,
    store: Annotated[AuthStore, Depends(_store)] = None,
) -> CurrentUser | None:
    return store.current_user(_bearer_token(authorization))


def require_current_user(
    user: Annotated[CurrentUser | None, Depends(optional_current_user)],
) -> CurrentUser:
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in with GitHub to continue")
    return user


def _allowed_return_to(value: str | None) -> str:
    allowed = set(load_cors_allow_origins())
    configured = os.environ.get("MERGEGATE_FRONTEND_URL")
    if configured:
        allowed.add(configured.rstrip("/"))
    if not allowed:
        raise HTTPException(
            status_code=503,
            detail="Set MERGEGATE_FRONTEND_URL before enabling GitHub sign-in",
        )
    candidate = (value or next(iter(allowed))).rstrip("/")
    parsed = urlparse(candidate)
    if parsed.scheme != "https" or candidate not in allowed:
        raise HTTPException(status_code=400, detail="Unapproved sign-in return URL")
    return candidate


def _oauth_settings() -> tuple[str, str]:
    client_id = os.environ.get("GITHUB_OAUTH_CLIENT_ID")
    client_secret = os.environ.get("GITHUB_OAUTH_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=503,
            detail="GitHub OAuth is not configured on this deployment",
        )
    return client_id, client_secret


def _callback_url() -> str:
    public_api_url = os.environ.get("MERGEGATE_PUBLIC_API_URL")
    if not public_api_url:
        raise HTTPException(
            status_code=503,
            detail="Set MERGEGATE_PUBLIC_API_URL before enabling GitHub sign-in",
        )
    return f"{public_api_url.rstrip('/')}/api/auth/github/callback"


def _github_json(
    url: str,
    payload: dict[str, str] | None = None,
    access_token: str | None = None,
) -> dict[str, object]:
    headers = {"Accept": "application/json", "User-Agent": "MergeGate"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=headers, method="POST" if data else "GET")
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - never expose provider response details
        raise HTTPException(
            status_code=502, detail="GitHub could not complete sign-in"
        ) from exc


def _github_token(payload: dict[str, str]) -> dict[str, object]:
    request = Request(
        _GITHUB_TOKEN_URL,
        data=urlencode(payload).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "MergeGate",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - never expose provider response details
        raise HTTPException(
            status_code=502, detail="GitHub could not complete sign-in"
        ) from exc


@router.get("/session")
def session(
    user: Annotated[CurrentUser | None, Depends(optional_current_user)],
) -> dict:
    if user is None:
        return {"authenticated": False}
    return {
        "authenticated": True,
        "user": {
            "id": user.id,
            "github_login": user.github_login,
            "avatar_url": user.avatar_url,
        },
    }


@router.get("/github/login")
def github_login(
    return_to: str | None = Query(default=None),
    store: Annotated[AuthStore, Depends(_store)] = None,
) -> RedirectResponse:
    client_id, _ = _oauth_settings()
    try:
        store.require_credential_storage()
    except AuthConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    state = store.create_oauth_state(_allowed_return_to(return_to))
    params = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": _callback_url(),
            "scope": "read:user repo",
            "state": state,
        }
    )
    return RedirectResponse(f"{_GITHUB_AUTHORIZE_URL}?{params}", status_code=302)


@router.get("/github/callback")
def github_callback(
    code: str,
    state: str,
    store: Annotated[AuthStore, Depends(_store)] = None,
) -> RedirectResponse:
    return_to = store.consume_oauth_state(state)
    client_id, client_secret = _oauth_settings()
    token_payload = _github_token(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": _callback_url(),
        },
    )
    access_token = token_payload.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise HTTPException(
            status_code=502, detail="GitHub did not issue an access token"
        )
    user_payload = _github_json(_GITHUB_USER_URL, access_token=access_token)
    github_id = user_payload.get("id")
    login = user_payload.get("login")
    if github_id is None or not isinstance(login, str):
        raise HTTPException(
            status_code=502, detail="GitHub did not return a user profile"
        )
    user = store.upsert_github_user(
        github_id=str(github_id),
        login=login,
        avatar_url=user_payload.get("avatar_url")
        if isinstance(user_payload.get("avatar_url"), str)
        else None,
        access_token=access_token,
    )
    session_token = store.create_session(user.id)
    return RedirectResponse(
        f"{return_to}/auth/callback#session={session_token}", status_code=302
    )


@router.post("/logout", status_code=204)
def logout(
    authorization: Annotated[str | None, Header()] = None,
    store: Annotated[AuthStore, Depends(_store)] = None,
) -> None:
    token = _bearer_token(authorization)
    if token:
        store.revoke_session(token)


@router.get("/connections")
def connections(
    user: Annotated[CurrentUser, Depends(require_current_user)],
    store: Annotated[AuthStore, Depends(_store)] = None,
) -> list[dict[str, str]]:
    return [summary.__dict__ for summary in store.list_connections(user.id)]


@router.put("/connections/{kind}", status_code=204)
def save_connection(
    kind: str,
    body: ConnectionRequest,
    user: Annotated[CurrentUser, Depends(require_current_user)],
    store: Annotated[AuthStore, Depends(_store)] = None,
) -> None:
    try:
        store.put_connection(user.id, kind, body.secret, body.label or kind)
    except (AuthConfigurationError, ConnectionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/connections/{kind}", status_code=204)
def delete_connection(
    kind: str,
    user: Annotated[CurrentUser, Depends(require_current_user)],
    store: Annotated[AuthStore, Depends(_store)] = None,
) -> None:
    store.delete_connection(user.id, kind)


@router.post("/github/repositories")
def connect_repository(
    body: RepositoryRequest,
    user: Annotated[CurrentUser, Depends(require_current_user)],
    store: Annotated[AuthStore, Depends(_store)] = None,
) -> dict[str, str]:
    try:
        path = store.clone_repository(user.id, body.full_name)
    except ConnectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"full_name": body.full_name, "repo_ref": str(path)}
