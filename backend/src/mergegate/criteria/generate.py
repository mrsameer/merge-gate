from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from mergegate.models import Contract, Criterion, CriterionType, ExpectedResult


def map_repo(repo_path: Path) -> dict[str, list[str]]:
    files: list[str] = []
    for path in repo_path.rglob("*"):
        if path.is_file() and ".git" not in path.parts:
            files.append(str(path.relative_to(repo_path)).replace("\\", "/"))
    return {"files": sorted(files)}


def generate_hybrid_criteria(
    *, run_id: str, objective: str, repo_path: Path
) -> Contract:
    repo_map = map_repo(repo_path)
    criteria = [
        Criterion(
            id="existing-tests",
            type=CriterionType.COMMAND,
            priority=10,
            command="python -m pytest -q",
            expected_exit_code=0,
            result_expected=ExpectedResult.PASS,
        ),
        Criterion(
            id="protected-files",
            type=CriterionType.GIT_POLICY,
            priority=20,
            params={"paths": ["app/auth/**"]},
            result_expected=ExpectedResult.PASS,
        ),
    ]
    if "idempotency" in objective.lower() or "order" in objective.lower():
        criteria.append(
            Criterion(
                id="feature-exists",
                type=CriterionType.ARCHITECTURE,
                priority=5,
                command=(
                    "python -c \"import pathlib; "
                    "assert 'Idempotency-Key' in "
                    "pathlib.Path('app/orders/router.py').read_text()\""
                ),
                expected_exit_code=0,
                result_expected=ExpectedResult.PASS,
            )
        )
    contract = Contract(
        id=str(uuid4()),
        run_id=run_id,
        mode="hybrid",
        criteria=criteria,
        approved=False,
    )
    contract.model_dump()  # validate
    _ = repo_map
    return contract
