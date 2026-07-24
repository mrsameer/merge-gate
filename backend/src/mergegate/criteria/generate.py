"""Read-only repository mapping and hybrid contract generation for US1."""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from mergegate.models import Contract, ContractMode, Criterion, CriterionType

_IGNORED_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
}
_MAX_FILE_SIZE_BYTES = 256 * 1024
_MAX_FILES = 500
_ROUTE_PATTERN = re.compile(r"@\w+\.(?:get|post|put|patch|delete)\(\s*[\"']([^\"']+)")


class RepositoryMappingError(ValueError):
    """The target repository cannot be safely mapped into a contract."""


class RepositoryFile(BaseModel):
    """A relevant, non-binary file discovered during read-only mapping."""

    model_config = ConfigDict(frozen=True)

    path: str
    role: str
    routes: tuple[str, ...] = ()


class RepositoryMap(BaseModel):
    """A bounded manifest used to ground generated criteria in real files."""

    model_config = ConfigDict(frozen=True)

    root: str
    files: tuple[RepositoryFile, ...] = Field(default_factory=tuple)

    def paths_for(self, role: str) -> tuple[str, ...]:
        return tuple(file.path for file in self.files if file.role == role)


def map_repository(repo_path: str | Path) -> RepositoryMap:
    """Return a bounded read-only manifest of source, test, config, and docs files."""

    root = Path(repo_path).resolve()
    if not root.is_dir():
        raise RepositoryMappingError(f"repository path is not a directory: {root}")

    mapped_files: list[RepositoryFile] = []
    for path in sorted(root.rglob("*")):
        if len(mapped_files) >= _MAX_FILES:
            break
        if not path.is_file() or any(
            part in _IGNORED_DIRECTORIES for part in path.parts
        ):
            continue
        try:
            if path.stat().st_size > _MAX_FILE_SIZE_BYTES:
                continue
        except OSError:
            continue

        relative_path = path.relative_to(root).as_posix()
        role = _classify_path(relative_path)
        if role is None:
            continue
        mapped_files.append(
            RepositoryFile(
                path=relative_path,
                role=role,
                routes=_find_routes(path) if role == "source" else (),
            )
        )

    return RepositoryMap(root=str(root), files=tuple(mapped_files))


def generate_hybrid_contract(
    *, objective: str, repo_map: RepositoryMap, run_id: str, contract_id: str
) -> Contract:
    """Create an editable hybrid draft whose assertions cite mapped repository files."""

    if not objective.strip():
        raise ValueError("objective must not be empty")

    source_paths = repo_map.paths_for("source")
    if not source_paths:
        raise RepositoryMappingError(
            "cannot generate grounded criteria without source files"
        )

    criteria: list[Criterion] = [
        Criterion(
            id="feature-exists",
            type=CriterionType.ARCHITECTURE,
            priority=1,
            description=f"Implement the requested behavior: {objective.strip()}",
            source_paths=[source_paths[0]],
        )
    ]

    test_paths = repo_map.paths_for("test")
    if test_paths:
        criteria.extend(
            (
                Criterion(
                    id="existing-tests",
                    type=CriterionType.COMMAND,
                    priority=2,
                    description="Existing repository tests pass.",
                    source_paths=list(test_paths),
                    command="pytest",
                    expected_exit_code=0,
                ),
                Criterion(
                    id="new-tests",
                    type=CriterionType.COMMAND,
                    priority=3,
                    description="Task-specific tests are added and pass.",
                    source_paths=list(test_paths),
                    command="pytest",
                    expected_exit_code=0,
                ),
            )
        )

    order_sources = tuple(path for path in source_paths if "order" in path.lower())
    if "idempot" in objective.lower() and order_sources:
        criteria.extend(
            (
                Criterion(
                    id="idempotency-key-required",
                    type=CriterionType.OPENAPI,
                    priority=4,
                    description="POST /orders requires an Idempotency-Key header.",
                    source_paths=[order_sources[0]],
                    params={"route": "/orders", "required_header": "Idempotency-Key"},
                ),
                Criterion(
                    id="idempotent-order-reuse",
                    type=CriterionType.DATABASE_ASSERTION,
                    priority=5,
                    description=(
                        "The same key and body return the original order "
                        "without another row."
                    ),
                    source_paths=[order_sources[0]],
                ),
                Criterion(
                    id="idempotency-key-conflict",
                    type=CriterionType.OPENAPI,
                    priority=6,
                    description="The same key with a different body returns HTTP 409.",
                    source_paths=[order_sources[0]],
                    params={"route": "/orders", "status_code": 409},
                ),
            )
        )

    return Contract(
        id=contract_id,
        run_id=run_id,
        mode=ContractMode.HYBRID,
        criteria=criteria,
    )


def _classify_path(relative_path: str) -> str | None:
    name = Path(relative_path).name.lower()
    parts = {part.lower() for part in Path(relative_path).parts}
    if "tests" in parts or name.startswith("test_") or name.endswith("_test.py"):
        return "test"
    if Path(relative_path).suffix.lower() in {".py", ".ts", ".tsx", ".js", ".jsx"}:
        return "source"
    if Path(relative_path).suffix.lower() in {".json", ".toml", ".yaml", ".yml"}:
        return "config"
    if Path(relative_path).suffix.lower() in {".md", ".rst"}:
        return "docs"
    return None


def _find_routes(path: Path) -> tuple[str, ...]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ()
    return tuple(_ROUTE_PATTERN.findall(text))
