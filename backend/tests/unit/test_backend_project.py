"""Project-init test for T002 — the backend `uv` project must declare its stack.

`plan.md` names the backend's primary dependencies (FastAPI, SSE, LangGraph +
its sqlite checkpointer, Pydantic, uvicorn, PyYAML, GitPython) and its Python
version floor. This test encodes that promise against `backend/pyproject.toml`
so the dependency set stays reviewable in one place and can't silently drift.
"""

import tomllib
from pathlib import Path

# <root>/backend/tests/unit/test_backend_project.py
BACKEND_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT_PATH = BACKEND_ROOT / "pyproject.toml"

EXPECTED_DEPENDENCY_PREFIXES: tuple[str, ...] = (
    "fastapi",
    "sse-starlette",
    "langgraph",
    "langgraph-checkpoint-sqlite",
    "pydantic",
    "uvicorn",
    "pyyaml",
    "gitpython",
)


def _load_pyproject() -> dict:
    with PYPROJECT_PATH.open("rb") as fh:
        return tomllib.load(fh)


def test_pyproject_exists() -> None:
    """The backend must be an initialized `uv` project."""
    assert PYPROJECT_PATH.is_file(), "backend/pyproject.toml is missing"


def test_pyproject_declares_expected_dependencies() -> None:
    """Every dependency named in plan.md must be declared."""
    data = _load_pyproject()
    dependencies = data["project"]["dependencies"]
    declared = {dep.lower() for dep in dependencies}

    missing = [
        prefix
        for prefix in EXPECTED_DEPENDENCY_PREFIXES
        if not any(dep.startswith(prefix) for dep in declared)
    ]
    assert not missing, "Missing dependencies from plan.md: " + ", ".join(missing)


def test_pyproject_requires_python_3_11_or_newer() -> None:
    """plan.md pins the backend to Python 3.11+."""
    data = _load_pyproject()
    requires_python = data["project"]["requires-python"]
    assert requires_python.startswith(">=3.11")
