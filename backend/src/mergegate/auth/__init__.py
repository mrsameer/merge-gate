"""Authentication, credential vaulting, and GitHub repository connections."""

from mergegate.auth.router import router
from mergegate.auth.store import AuthStore, CurrentUser, get_auth_store

__all__ = ["AuthStore", "CurrentUser", "get_auth_store", "router"]
