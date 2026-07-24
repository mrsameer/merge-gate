"""Shared fixtures for the demo-repo order service test suite."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.auth.security import API_KEY


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"X-API-Key": API_KEY}
