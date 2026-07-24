"""Protected module — the acceptance loop must NEVER modify this file.

Guards `app/orders` with a static API-key check. Deliberately simple: this
fixture's job is to prove that generated changes stay out of protected paths,
not to demonstrate a production auth scheme.
"""

from typing import Annotated

from fastapi import Header, HTTPException, status

API_KEY = "demo-secret-key"


def require_api_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    """Raise 401 unless the caller presents the correct `X-API-Key` header."""
    if x_api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
