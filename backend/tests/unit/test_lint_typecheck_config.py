"""Config test for T004 — backend must have ruff + pyright configured.

tasks.md T004 requires ruff (lint/format) and pyright (type checking) to be
set up for the backend. This test encodes that promise against
`backend/pyproject.toml` so the tooling can't silently disappear.
"""

import tomllib
from pathlib import Path

# <root>/backend/tests/unit/test_lint_typecheck_config.py
BACKEND_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT_PATH = BACKEND_ROOT / "pyproject.toml"


def _load_pyproject() -> dict:
    with PYPROJECT_PATH.open("rb") as fh:
        return tomllib.load(fh)


def test_ruff_and_pyright_declared_as_dev_dependencies() -> None:
    """ruff and pyright must be installable via `uv sync` for every contributor."""
    data = _load_pyproject()
    dev_deps = {dep.lower() for dep in data["dependency-groups"]["dev"]}

    missing = [
        prefix
        for prefix in ("ruff", "pyright")
        if not any(dep.startswith(prefix) for dep in dev_deps)
    ]
    assert not missing, "Missing dev dependencies: " + ", ".join(missing)


def test_ruff_config_present_with_line_length_88() -> None:
    """Ruff must be configured with the repo's 88-char line length."""
    data = _load_pyproject()
    ruff_config = data.get("tool", {}).get("ruff")
    assert ruff_config is not None, "Missing [tool.ruff] section in pyproject.toml"
    assert ruff_config.get("line-length") == 88


def test_pyright_config_present() -> None:
    """Pyright must be configured to scan the backend source tree."""
    data = _load_pyproject()
    pyright_config = data.get("tool", {}).get("pyright")
    assert pyright_config is not None, (
        "Missing [tool.pyright] section in pyproject.toml"
    )
    assert "src" in pyright_config.get("include", [])
