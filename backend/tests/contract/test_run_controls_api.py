"""T062 [US7] pause, resume, and stop REST contract tests."""

from mergegate.api.store import store
from mergegate.models import RunStatus
from mergegate.models.enums import LedgerEntryType


def test_pause_resume_stop_transitions_are_truthful(client, run_id):
    record = store.get_run(run_id)
    assert record is not None
    record.run.status = RunStatus.RUNNING

    paused = client.post(f"/api/runs/{run_id}:pause")
    assert paused.status_code == 200, paused.text
    assert paused.json()["status"] == "paused"

    resumed = client.post(f"/api/runs/{run_id}:resume")
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["status"] == "running"

    stopped = client.post(f"/api/runs/{run_id}:stop")
    assert stopped.status_code == 200, stopped.text
    assert stopped.json()["status"] == "CANCELLED"
    assert stopped.json()["ended_at"] is not None
    assert record.ledger is not None
    terminal_entries = [
        entry
        for entry in record.ledger.read_entries()
        if entry.type == LedgerEntryType.TERMINAL
    ]
    assert len(terminal_entries) == 1
    assert terminal_entries[0].payload == {
        "status": "CANCELLED",
        "reason": "stopped by operator",
    }


def test_pause_and_resume_reject_invalid_states(client, run_id):
    paused = client.post(f"/api/runs/{run_id}:pause")
    assert paused.status_code == 409, paused.text

    resumed = client.post(f"/api/runs/{run_id}:resume")
    assert resumed.status_code == 409, resumed.text
