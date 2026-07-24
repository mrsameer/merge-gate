"""Unit tests for T022/T023 repository-grounded contracts and freeze semantics."""

import os
from pathlib import Path

import pytest

from mergegate.criteria.contract import (
    ContractStateError,
    approve_contract,
    edit_draft,
    verify_frozen_contract,
)
from mergegate.criteria.generate import (
    RepositoryMappingError,
    generate_hybrid_contract,
    map_repository,
)
from mergegate.models import Contract


@pytest.fixture
def mapped_demo_repo(tmp_path: Path):
    (tmp_path / "app" / "orders").mkdir(parents=True)
    (tmp_path / "tests").mkdir()
    (tmp_path / ".git").mkdir()
    (tmp_path / "app" / "orders" / "routes.py").write_text(
        '@router.post("/orders")\ndef create_order():\n    pass\n', encoding="utf-8"
    )
    (tmp_path / "tests" / "test_orders.py").write_text(
        "def test_orders(): pass\n", encoding="utf-8"
    )
    (tmp_path / ".git" / "hidden.py").write_text("not source\n", encoding="utf-8")
    return map_repository(tmp_path)


def test_repository_map_is_grounded_and_ignores_git(mapped_demo_repo) -> None:
    paths = {file.path for file in mapped_demo_repo.files}
    assert "app/orders/routes.py" in paths
    assert "tests/test_orders.py" in paths
    assert ".git/hidden.py" not in paths
    source_file = next(
        file for file in mapped_demo_repo.files if file.path == "app/orders/routes.py"
    )
    assert source_file.routes == ("/orders",)


def test_hybrid_contract_is_draft_and_uses_existing_paths(mapped_demo_repo) -> None:
    contract = generate_hybrid_contract(
        objective="Make POST /orders idempotent",
        repo_map=mapped_demo_repo,
        run_id="run-1",
        contract_id="contract-1",
    )

    paths = {file.path for file in mapped_demo_repo.files}
    assert contract.mode == "hybrid"
    assert not contract.approved
    assert contract.frozen_hash is None
    assert [criterion.priority for criterion in contract.criteria] == sorted(
        criterion.priority for criterion in contract.criteria
    )
    assert all(
        set(criterion.source_paths).issubset(paths) for criterion in contract.criteria
    )
    assert {criterion.id for criterion in contract.criteria} >= {
        "idempotency-key-required",
        "idempotent-order-reuse",
        "idempotency-key-conflict",
    }


def test_approval_is_stable_and_freezes_editing(mapped_demo_repo) -> None:
    draft = generate_hybrid_contract(
        objective="Make POST /orders idempotent",
        repo_map=mapped_demo_repo,
        run_id="run-1",
        contract_id="contract-1",
    )
    approved = approve_contract(draft)

    assert approved.approved
    assert approved.frozen_hash
    assert approve_contract(approved) == approved
    assert verify_frozen_contract(approved)
    with pytest.raises(ContractStateError):
        edit_draft(approved, approved.criteria)


def test_tampered_frozen_contract_fails_verification(mapped_demo_repo) -> None:
    approved = approve_contract(
        generate_hybrid_contract(
            objective="Make POST /orders idempotent",
            repo_map=mapped_demo_repo,
            run_id="run-1",
            contract_id="contract-1",
        )
    )
    changed_criterion = approved.criteria[0].model_copy(
        update={"description": "Different goal"}
    )
    tampered = approved.model_copy(
        update={"criteria": (changed_criterion, *approved.criteria[1:])}
    )

    assert not verify_frozen_contract(tampered)


def test_empty_draft_cannot_be_created_or_approved() -> None:
    with pytest.raises(ValueError, match="at least 1 item"):
        Contract(id="contract-1", run_id="run-1", criteria=[])


def test_repository_map_tolerates_cache_directory_deleted_during_scan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "app.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    transient = tmp_path / "pytest-cache-files-race"
    transient.mkdir()
    (transient / "leftover.py").write_text("VALUE = 2\n", encoding="utf-8")
    real_scandir = os.scandir
    deleted = False

    def flaky_scandir(path):
        nonlocal deleted
        if Path(path) == transient and not deleted:
            deleted = True
            (transient / "leftover.py").unlink()
            transient.rmdir()
            raise FileNotFoundError(str(transient))
        return real_scandir(path)

    monkeypatch.setattr(os, "scandir", flaky_scandir)

    mapped = map_repository(tmp_path)

    assert {entry.path for entry in mapped.files} == {"app.py"}


def test_repository_map_does_not_hide_stable_scan_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    locked = tmp_path / "locked"
    locked.mkdir()
    real_scandir = os.scandir

    def denied_scandir(path):
        if Path(path) == locked:
            raise PermissionError(f"permission denied: {locked}")
        return real_scandir(path)

    monkeypatch.setattr(os, "scandir", denied_scandir)

    with pytest.raises(RepositoryMappingError, match="permission denied"):
        map_repository(tmp_path)
