"""FastAPI control-plane app: skeleton, router wiring, and error envelope.

Owns the `FastAPI` instance, the `/api` mount point, and the uniform
`{"error": {"code", "message"}}` envelope required by
`specs/001-mergegate-control-plane/contracts/control-plane-api.md`. Feature
routers (runs, workflows, events) attach to `api_router` as their own tasks
land.
"""

from __future__ import annotations

from http import HTTPStatus

from fastapi import APIRouter, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from mergegate.api.events import router as events_router
from mergegate.api.runs import router as runs_router
from mergegate.api.workflows import router as workflows_router

app = FastAPI(title="MergeGate Control Plane")

api_router = APIRouter(prefix="/api")


@api_router.get("/health")
def health() -> dict[str, str]:
    """Liveness probe proving the router is wired into the app."""
    return {"status": "ok"}


api_router.include_router(events_router)
api_router.include_router(workflows_router)
api_router.include_router(runs_router)

app.include_router(api_router)


def _error_code(status_code: int) -> str:
    """Map an HTTP status code to an upper-snake-case error code."""
    try:
        return HTTPStatus(status_code).phrase.upper().replace(" ", "_")
    except ValueError:
        return "ERROR"


@app.exception_handler(StarletteHTTPException)
async def handle_http_exception(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Wrap HTTPException (raised by routes or unmatched routing) in the envelope."""
    message = (
        exc.detail if isinstance(exc.detail, str) else _error_code(exc.status_code)
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": _error_code(exc.status_code), "message": message}},
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Wrap request validation failures in the error envelope."""
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed.",
            }
        },
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Wrap any unhandled exception in a 500 error envelope."""
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred.",
            }
        },
    )
