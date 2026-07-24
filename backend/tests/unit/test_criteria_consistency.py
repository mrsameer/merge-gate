"""T045 [US4] — deterministic contract consistency detection."""

from mergegate.criteria.consistency import detect_inconsistency
from mergegate.models import Contract, Criterion, CriterionType


def _contract(*criteria: Criterion) -> Contract:
    return Contract(id="contract-1", run_id="run-1", criteria=list(criteria))


def test_detects_explicitly_contradictory_statuses_in_one_criterion() -> None:
    issue = detect_inconsistency(
        _contract(
            Criterion(
                id="response-status",
                type=CriterionType.OPENAPI,
                priority=1,
                description=(
                    "The same successful request must return both 200 and 201."
                ),
            )
        )
    )

    assert issue is not None
    assert issue.conflicting_criteria == ("response-status",)
    assert "HTTP 200" in issue.reason
    assert "HTTP 201" in issue.reason


def test_detects_ambiguous_status_choice() -> None:
    issue = detect_inconsistency(
        _contract(
            Criterion(
                id="response-status",
                type=CriterionType.OPENAPI,
                priority=1,
                description="Return either HTTP 200 or HTTP 201 on success.",
            )
        )
    )

    assert issue is not None
    assert "ambiguous" in issue.reason


def test_detects_same_command_with_mutually_exclusive_exit_codes() -> None:
    issue = detect_inconsistency(
        _contract(
            Criterion(
                id="command-passes",
                type=CriterionType.COMMAND,
                priority=1,
                command="pytest -q",
                expected_exit_code=0,
            ),
            Criterion(
                id="command-fails",
                type=CriterionType.COMMAND,
                priority=2,
                command="pytest -q",
                expected_exit_code=1,
            ),
        )
    )

    assert issue is not None
    assert issue.conflicting_criteria == ("command-passes", "command-fails")
    assert "exit with both 0 and 1" in issue.reason


def test_allows_distinct_statuses_for_distinct_request_conditions() -> None:
    issue = detect_inconsistency(
        _contract(
            Criterion(
                id="created",
                type=CriterionType.OPENAPI,
                priority=1,
                params={
                    "route": "/orders",
                    "condition": "new idempotency key",
                    "status_code": 201,
                },
            ),
            Criterion(
                id="replayed",
                type=CriterionType.OPENAPI,
                priority=2,
                params={
                    "route": "/orders",
                    "condition": "existing idempotency key",
                    "status_code": 200,
                },
            ),
        )
    )

    assert issue is None
