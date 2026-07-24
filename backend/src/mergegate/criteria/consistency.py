from __future__ import annotations

from mergegate.models import ClarificationConflict, ClarificationRequest, Contract


def detect_contradictions(
    contract: Contract, *, objective: str = ""
) -> ClarificationRequest | None:
    conflicts: list[ClarificationConflict] = []

    status_by_endpoint: dict[str, list[tuple[str, int]]] = {}
    for criterion in contract.criteria:
        if criterion.params.get("check") != "status_code":
            continue
        endpoint = str(criterion.params.get("endpoint", ""))
        status = criterion.params.get("http_status")
        if not endpoint or status is None:
            continue
        status_by_endpoint.setdefault(endpoint, []).append(
            (criterion.id, int(status))
        )

    for endpoint, entries in status_by_endpoint.items():
        statuses = {status for _, status in entries}
        if len(statuses) > 1:
            criteria_ids = [criterion_id for criterion_id, _ in entries]
            status_list = sorted(statuses)
            conflicts.append(
                ClarificationConflict(
                    kind="conflicting_http_status",
                    criteria_ids=criteria_ids,
                    detail=(
                        f"Endpoint {endpoint} requires incompatible status codes: "
                        f"{status_list}"
                    ),
                )
            )

    if not conflicts:
        return None

    return ClarificationRequest(
        reason="conflicting_criteria",
        message=conflicts[0].detail,
        conflicts=conflicts,
        objective=objective,
    )
