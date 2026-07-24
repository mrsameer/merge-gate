"""T069 container packaging contract.

The Compose stack is part of the demo surface: it must expose the control
plane, serve the browser UI, and keep the target repository runner separate.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
COMPOSE_FILE = ROOT / "docker-compose.yml"


def _compose() -> dict:
    return yaml.safe_load(COMPOSE_FILE.read_text())


def test_compose_defines_healthy_control_plane_ui_and_demo_runner() -> None:
    config = _compose()
    services = config["services"]

    assert set(services) == {"backend", "frontend", "demo-repo-runner"}
    assert all(service.get("healthcheck") for service in services.values())
    assert services["frontend"]["depends_on"]["backend"]["condition"] == (
        "service_healthy"
    )
    assert services["backend"]["depends_on"]["demo-repo-runner"]["condition"] == (
        "service_healthy"
    )

    assert services["backend"]["build"]["dockerfile"] == "backend/Dockerfile"
    assert services["frontend"]["build"]["dockerfile"] == "frontend/Dockerfile"
    assert services["demo-repo-runner"]["build"]["dockerfile"] == (
        "demo-repo/Dockerfile"
    )


def test_compose_does_not_embed_credentials_or_secret_values() -> None:
    text = COMPOSE_FILE.read_text()

    assert "GOOGLE_API_KEY" not in text
    assert "GEMINI_API_KEY" not in text
    assert "application_default_credentials.json" not in text
    assert "PRIVATE KEY" not in text


def test_container_build_inputs_and_reverse_proxy_are_present() -> None:
    required = {
        ROOT / ".dockerignore",
        ROOT / "backend" / "Dockerfile",
        ROOT / "frontend" / "Dockerfile",
        ROOT / "frontend" / "nginx.conf",
        ROOT / "demo-repo" / "Dockerfile",
    }

    assert not sorted(str(path) for path in required if not path.is_file())


def test_docker_compose_configuration_resolves() -> None:
    if shutil.which("docker") is None:
        pytest.skip("Docker CLI is not installed")

    result = subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "config", "--quiet"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
