"""Local provider-environment loading shared by API startup and adapters."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv


def load_local_env(path: Path | None = None) -> bool:
    """Load ``backend/.env`` without overriding explicitly exported values."""
    dotenv_path = path or Path(__file__).resolve().parents[3] / ".env"
    return load_dotenv(dotenv_path, override=False)
