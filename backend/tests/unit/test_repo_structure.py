"""Structure test for T001 — the monorepo layout must match plan.md.

This test encodes the "Source Code (repository root)" tree from
`specs/001-mergegate-control-plane/plan.md`. It is the red-before/green-after
acceptance for creating the scaffold: every directory the plan promises must
exist so later tasks have a home. Keeping the expected paths in one list makes
the intended layout reviewable at a glance and guards against accidental
renames as the project grows.
"""

from pathlib import Path

# Repository root is three levels up from this file:
# <root>/backend/tests/unit/test_repo_structure.py
REPO_ROOT = Path(__file__).resolve().parents[3]

# The directory tree promised by plan.md, relative to the repository root.
EXPECTED_DIRS: tuple[str, ...] = (
    # backend/
    "backend/src/mergegate/api",
    "backend/src/mergegate/orchestrator",
    "backend/src/mergegate/acceptance",
    "backend/src/mergegate/harness",
    "backend/src/mergegate/workspace",
    "backend/src/mergegate/ledger",
    "backend/src/mergegate/criteria",
    "backend/src/mergegate/models",
    "backend/src/mergegate/config",
    "backend/tests/contract",
    "backend/tests/integration",
    "backend/tests/unit",
    # frontend/
    "frontend/src/canvas",
    "frontend/src/inspector",
    "frontend/src/console",
    "frontend/src/evidence",
    "frontend/src/state",
    "frontend/src/api",
    "frontend/tests",
    # demo-repo/ (the target task fixture)
    "demo-repo/app/orders",
    "demo-repo/app/auth",
    "demo-repo/tests",
)


def test_all_expected_directories_exist() -> None:
    """Every directory promised by plan.md must be present in the repo."""
    missing = [rel for rel in EXPECTED_DIRS if not (REPO_ROOT / rel).is_dir()]
    assert not missing, "Missing directories from plan.md layout: " + ", ".join(
        sorted(missing)
    )
