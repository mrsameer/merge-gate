from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    demo_repo_path: Path
    harness_provider: str
    default_workflow_id: str


def get_settings() -> Settings:
    root = Path(__file__).resolve().parents[4]
    return Settings(
        data_dir=Path(os.environ.get("MERGEGATE_DATA_DIR", root / ".mergegate-data")),
        demo_repo_path=Path(
            os.environ.get("MERGEGATE_DEMO_REPO_PATH", root / "demo-repo")
        ),
        harness_provider=os.environ.get("MERGEGATE_HARNESS_PROVIDER", "stub"),
        default_workflow_id=os.environ.get(
            "MERGEGATE_DEFAULT_WORKFLOW_ID", "default-four-role-loop"
        ),
    )
