"""T062 [US7] pause, resume, and stop REST contract tests."""

from mergegate.api.store import store
from mergegate.models import Attempt, RunStatus
from mergegate.models.enums import LedgerEntryType
from mergegate.workspace.worktree import Worktree


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


def test_stop_discards_an_unmerged_final_attempt(client, run_id, monkeypatch):
    record = store.get_run(run_id)
    assert record is not None
    record.run.status = RunStatus.AWAITING_GATE
    record.run.attempts.append(
        Attempt(
            id="attempt-1",
            run_id=run_id,
            index=1,
            worktree_path="/tmp/mergegate-worktree",
            branch="mergegate/run-1/attempt-1",
            diff="",
            harness_log="done",
        )
    )
    discarded: list[Worktree] = []
    monkeypatch.setattr(
        "mergegate.api.runs.discard_worktree", discarded.append
    )

    stopped = client.post(f"/api/runs/{run_id}:stop")

    assert stopped.status_code == 200, stopped.text
    assert len(discarded) == 1
    assert str(discarded[0].path) == record.run.attempts[-1].worktree_path
