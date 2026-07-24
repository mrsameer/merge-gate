from __future__ import annotations

from datetime import UTC, datetime

from mergegate.ledger.store import RunStore
from mergegate.models import Run, RunStatus


def approve_final_gate(run: Run, store: RunStore) -> Run:
    if run.status != RunStatus.AWAITING_FINAL_GATE:
        raise ValueError("run is not awaiting final gate")
    run.status = RunStatus.SUCCESS
    run.ended_at = datetime.now(tz=UTC)
    store.ledger.append(
        run.id,
        "terminal",
        {"state": RunStatus.SUCCESS, "branch_ref": run.branch_ref},
    )
    return store.save(run)
