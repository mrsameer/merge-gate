from __future__ import annotations

import os
from pathlib import Path

from mergegate.config.environment import load_local_env


def test_load_local_env_preserves_explicit_environment(
    monkeypatch, tmp_path: Path
) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("MG_LOCAL=from-dotenv\nMG_EXPLICIT=from-dotenv\n")
    monkeypatch.delenv("MG_LOCAL", raising=False)
    monkeypatch.setenv("MG_EXPLICIT", "from-shell")

    assert load_local_env(dotenv_path)
    assert os.environ["MG_LOCAL"] == "from-dotenv"
    assert os.environ["MG_EXPLICIT"] == "from-shell"
