from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from mergegate.models import Contract, Criterion, CriterionType, ExpectedResult


def _is_contradictory_status_objective(objective: str) -> bool:
    lower = objective.lower()
    return (
        "200" in lower
        and "201" in lower
        and ("both" in lower or "same successful" in lower or "same request" in lower)
    )


def _contradictory_status_criteria() -> list[Criterion]:
    endpoint = "POST /orders"
    return [
        Criterion(
            id="response-status-200",
            type=CriterionType.COMMAND,
            priority=1,
            params={
                "check": "status_code",
                "endpoint": endpoint,
                "http_status": 200,
            },
            result_expected=ExpectedResult.PASS,
        ),
        Criterion(
            id="response-status-201",
            type=CriterionType.COMMAND,
            priority=2,
            params={
                "check": "status_code",
                "endpoint": endpoint,
                "http_status": 201,
            },
            result_expected=ExpectedResult.PASS,
        ),
    ]


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
    criteria: list[Criterion] = []
    if _is_contradictory_status_objective(objective):
        criteria.extend(_contradictory_status_criteria())
    criteria.extend(
        [
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
    )
    if "idempotency" in objective.lower() or "order" in objective.lower():
        criteria.insert(
            0,
            Criterion(
                id="task-tests",
                type=CriterionType.COMMAND,
                priority=1,
                command="python -m pytest tests/test_idempotency.py -q",
                expected_exit_code=0,
                baseline_expected=ExpectedResult.FAIL,
                result_expected=ExpectedResult.PASS,
            ),
        )
        criteria.append(
            Criterion(
                id="feature-exists",
                type=CriterionType.ARCHITECTURE,
                priority=5,
                command=(
                    'python -c "import pathlib; '
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
