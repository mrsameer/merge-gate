"""Scaffold test for T005 — the `demo-repo/` order service fixture.

tasks.md T005 requires a self-contained FastAPI order service at `demo-repo/`
with `app/orders/`, a protected `app/auth/`, and a fast pytest suite. This
test encodes that promise so the fixture can't silently disappear or drift
from research.md R11 (idempotent `POST /orders` seed task, `app/auth/**`
protected).
"""

import tomllib
from pathlib import Path

# <root>/backend/tests/unit/test_demo_repo_scaffold.py
REPO_ROOT = Path(__file__).resolve().parents[3]
DEMO_REPO_ROOT = REPO_ROOT / "demo-repo"
PYPROJECT_PATH = DEMO_REPO_ROOT / "pyproject.toml"


def _load_pyproject() -> dict:
    with PYPROJECT_PATH.open("rb") as fh:
        return tomllib.load(fh)


def test_demo_repo_pyproject_exists() -> None:
    """demo-repo must be an initialized, independent Python project."""
    assert PYPROJECT_PATH.is_file(), "demo-repo/pyproject.toml is missing"


def test_demo_repo_declares_fastapi_and_uvicorn() -> None:
    data = _load_pyproject()
    declared = {dep.lower() for dep in data["project"]["dependencies"]}

    missing = [
        prefix
        for prefix in ("fastapi", "uvicorn")
        if not any(dep.startswith(prefix) for dep in declared)
    ]
    assert not missing, "Missing dependencies from research.md R11: " + ", ".join(
        missing
    )


def test_demo_repo_declares_pytest_as_dev_dependency() -> None:
    data = _load_pyproject()
    dev_deps = {dep.lower() for dep in data["dependency-groups"]["dev"]}
    assert any(dep.startswith("pytest") for dep in dev_deps), (
        "demo-repo must declare pytest so its suite is runnable via `uv run pytest`"
    )


def test_demo_repo_app_module_layout() -> None:
    """`app/orders` and `app/auth` must be real Python packages, not empty dirs."""
    expected_files = (
        "app/__init__.py",
        "app/main.py",
        "app/orders/__init__.py",
        "app/orders/router.py",
        "app/auth/__init__.py",
        "app/auth/security.py",
    )
    missing = [rel for rel in expected_files if not (DEMO_REPO_ROOT / rel).is_file()]
    assert not missing, "Missing demo-repo app files: " + ", ".join(missing)


def test_demo_repo_has_a_pytest_suite() -> None:
    test_files = list((DEMO_REPO_ROOT / "tests").glob("test_*.py"))
    assert test_files, "demo-repo/tests must contain at least one pytest test module"
