from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mergegate.api.runs import create_app
from mergegate.config.settings import Settings


def _patch_settings(settings: Settings) -> None:
    import mergegate.api.runs as runs_module
    import mergegate.config.settings as settings_module
    import mergegate.orchestrator.runner as runner_module

    def _get_settings() -> Settings:
        return settings

    settings_module.get_settings = _get_settings
    runs_module.get_settings = _get_settings
    runner_module.get_settings = _get_settings


def _integration_settings(
    tmp_path: Path, *, harness_provider: str = "stub"
) -> Settings:
    repo_root = Path(__file__).resolve().parents[3]
    return Settings(
        data_dir=tmp_path / "data",
        demo_repo_path=repo_root / "demo-repo",
        harness_provider=harness_provider,
        default_workflow_id="default-four-role-loop",
    )


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("MERGEGATE_HARNESS_PROVIDER", "stub")
    _patch_settings(_integration_settings(tmp_path, harness_provider="stub"))
    return TestClient(create_app())


@pytest.fixture
def client_fail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("MERGEGATE_HARNESS_PROVIDER", "stub-fail")
    _patch_settings(_integration_settings(tmp_path, harness_provider="stub-fail"))
    return TestClient(create_app())


@pytest.fixture
def client_no_progress(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("MERGEGATE_HARNESS_PROVIDER", "stub-no-progress")
    _patch_settings(
        _integration_settings(tmp_path, harness_provider="stub-no-progress")
    )
    return TestClient(create_app())


@pytest.fixture
def client_policy_auth(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("MERGEGATE_HARNESS_PROVIDER", "stub-policy-auth")
    _patch_settings(
        _integration_settings(tmp_path, harness_provider="stub-policy-auth")
    )
    return TestClient(create_app())


@pytest.fixture
def client_policy_skip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("MERGEGATE_HARNESS_PROVIDER", "stub-policy-skip")
    _patch_settings(
        _integration_settings(tmp_path, harness_provider="stub-policy-skip")
    )
    return TestClient(create_app())
