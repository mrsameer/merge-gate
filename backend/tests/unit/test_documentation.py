"""T070 documentation contracts: links, commands, architecture, and demo timing."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import unquote

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
README = REPO_ROOT / "README.md"
ARCHITECTURE = REPO_ROOT / "docs" / "architecture.md"
DEMO_SCRIPT = REPO_ROOT / "docs" / "demo-script.md"
DOCUMENTS = (README, ARCHITECTURE, DEMO_SCRIPT)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _local_markdown_links(path: Path) -> list[Path]:
    links: list[Path] = []
    for raw_target in re.findall(r"(?<!!)\[[^\]]+\]\(([^)]+)\)", _read(path)):
        target = raw_target.strip().strip("<>").split("#", 1)[0]
        if not target or re.match(r"^[a-z][a-z0-9+.-]*:", target):
            continue
        links.append((path.parent / unquote(target)).resolve())
    return links


def _seconds(minutes: str, seconds: str) -> int:
    return int(minutes) * 60 + int(seconds)


def test_documentation_files_and_local_links_exist() -> None:
    missing_documents = [path for path in DOCUMENTS if not path.is_file()]
    assert missing_documents == []

    missing_links = [
        (document.relative_to(REPO_ROOT), target)
        for document in DOCUMENTS
        for target in _local_markdown_links(document)
        if not target.exists()
    ]
    assert missing_links == []


def test_readme_setup_commands_match_project_entrypoints() -> None:
    readme = _read(README)
    package = json.loads(_read(REPO_ROOT / "frontend" / "package.json"))
    compose = yaml.safe_load(_read(REPO_ROOT / "docker-compose.yml"))
    dockerignore = _read(REPO_ROOT / ".dockerignore").splitlines()

    assert readme.startswith("# MergeGate\n")
    for command in (
        "uv sync --frozen",
        "uv run uvicorn mergegate.api.main:app --reload --port 8000",
        "npm ci",
        "npm run dev",
        "docker compose up --build --wait",
        "docker compose ps",
        "docker compose down",
        "curl --fail http://localhost:8000/api/health",
        "curl --fail http://localhost:9000/openapi.json",
    ):
        assert command in readme

    assert {"dev", "build", "test", "lint", "format:check"} <= package["scripts"].keys()
    assert set(compose["services"]) == {"backend", "frontend", "demo-repo-runner"}
    assert compose["services"]["frontend"]["ports"] == ["5173:80"]
    assert "**/._*" in dockerignore


def test_readme_documents_vertex_adc_terminal_states_and_limitations() -> None:
    readme = _read(README)

    for required in (
        "gcloud auth application-default login",
        "GOOGLE_GENAI_USE_VERTEXAI=true",
        "GOOGLE_CLOUD_PROJECT",
        "GOOGLE_CLOUD_LOCATION=asia-south1",
        "gemini-2.5-flash",
        "CLARIFICATION_REQUIRED",
        "HUMAN_REJECTED",
        "EXHAUSTED",
        "NO_PROGRESS",
        "TIMED_OUT",
        "POLICY_BLOCKED",
        "CANCELLED",
        "process-local",
        "backend restart",
    ):
        assert required in readme

    assert re.search(r"(?i)never commit.+credential|credential.+never commit", readme)
    assert "GEMINI_API_KEY=" not in readme


def test_architecture_diagram_keeps_generation_and_acceptance_separate() -> None:
    architecture = _read(ARCHITECTURE)

    assert "```mermaid" in architecture
    for boundary in (
        "React",
        "FastAPI",
        "Orchestrator",
        "Harness adapters",
        "Disposable git worktree",
        "LLM-free acceptance engine",
        "Hash-chained ledger",
        "SQLite",
        "SSE",
        "zero model calls",
    ):
        assert boundary in architecture

    assert "Harness --> Verdict" not in architecture
    assert "Acceptance --> Verdict" in architecture


def test_demo_script_is_exactly_six_minutes_and_covers_track_b() -> None:
    script = _read(DEMO_SCRIPT)
    windows = [
        (_seconds(*match[:2]), _seconds(*match[2:]))
        for match in re.findall(
            r"^## \[(\d+):(\d{2})–(\d+):(\d{2})\]", script, re.MULTILINE
        )
    ]

    assert windows
    assert windows[0][0] == 0
    assert windows[-1][1] == 6 * 60
    assert all(
        end == next_start for (_, end), (next_start, _) in zip(windows, windows[1:])
    )
    assert all(start < end for start, end in windows)

    for beat in range(1, 10):
        assert re.search(rf"^\|\s*{beat}\s*\|", script, re.MULTILINE)

    for truthful_claim in (
        "baseline red is not a failed execution attempt",
        "failed execution attempt",
        "structured feedback",
        "safe stop",
        "SUCCESS",
        "acceptance_hash",
        "zero model calls",
        "No execution attempt was created",
    ):
        assert truthful_claim in script
