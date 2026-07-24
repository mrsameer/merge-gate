"""T067 — ten-scenario reliability suite required by SC-011.

The scenarios intentionally exercise public control-plane boundaries where
operator-visible truth matters and the run driver directly where deterministic
fault injection is required.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path
from typing import cast
from uuid import uuid4

import anyio
import pytest
from starlette.requests import Request

from mergegate.acceptance.commands import COMMAND_NOT_FOUND_EXIT_CODE, run_command
from mergegate.harness.base import HarnessResult
from mergegate.models import (
    Budget,
    CheckStep,
    Contract,
    ContractMode,
    CostAccounting,
    Criterion,
    CriterionType,
    PassFail,
    Policy,
    Run,
    RunStatus,
)
from mergegate.orchestrator import gates, nodes
from mergegate.orchestrator.nodes import RunContext, drive_run
from mergegate.workspace.worktree import Worktree, capture_diff

PY = sys.executable


def _git(repo: Path, *args: str) -> None:
    result = run_command(["git", *args], cwd=repo)
    assert result.succeeded, result.stderr


@pytest.fixture()
def reliability_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "target"
    repo.mkdir()
    (repo / "app" / "auth").mkdir(parents=True)
    (repo / "app" / "auth" / "security.py").write_text(
        "TOKEN = 'safe'\n", encoding="utf-8"
    )
    (repo / "seed.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "reliability@example.com")
    _git(repo, "config", "user.name", "Reliability Test")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "baseline")
    return repo


def _contract(run_id: str, command: str) -> Contract:
    return Contract(
        id=f"contract-{run_id}",
        run_id=run_id,
        mode=ContractMode.HYBRID,
        approved=True,
        frozen_hash="frozen-reliability-contract",
        criteria=[
            Criterion(
                id="task-tests",
                type=CriterionType.COMMAND,
                priority=1,
                command=command,
                baseline_expected=PassFail.FAIL,
                result_expected=PassFail.PASS,
                step=CheckStep.NEW_TESTS,
            )
        ],
    )


def _run(repo: Path, *, max_attempts: int = 3) -> Run:
    return Run(
        id=f"run-reliability-{uuid4()}",
        workflow_id="workflow-reliability",
        objective="make the reliability criterion pass",
        repo_ref=str(repo),
        status=RunStatus.RUNNING,
        budgets=Budget(
            max_attempts=max_attempts,
            max_wall_clock_s=30,
            max_model_calls=20,
        ),
        current_attempt=0,
        cost=CostAccounting(),
    )


def _context(
    run: Run,
    repo: Path,
    contract: Contract,
    tmp_path: Path,
    *,
    policy: Policy | None = None,
    events: list[tuple[str, dict]] | None = None,
) -> RunContext:
    return RunContext(
        run=run,
        contract=contract,
        policy=policy or Policy(),
        provider="reliability",
        repo_ref=str(repo),
        worktrees_root=tmp_path / "worktrees",
        on_event=(
            (lambda kind, payload: events.append((kind, payload)))
            if events is not None
            else None
        ),
    )


class _AdaptiveHarness:
    def __init__(self) -> None:
        self.feedback = []

    def propose_changes(
        self,
        objective: str,
        feedback,
        workspace: Worktree,
    ) -> HarnessResult:
        self.feedback.append(feedback)
        value = 1 if feedback is None else 2
        (workspace.path / "feature.py").write_text(
            f"VALUE = {value}\n", encoding="utf-8"
        )
        diff = capture_diff(workspace)
        return HarnessResult(diff=diff.patch, changed_files=diff.changed_files)


class _SingleSuccessHarness:
    def propose_changes(
        self,
        objective: str,
        feedback,
        workspace: Worktree,
    ) -> HarnessResult:
        (workspace.path / "feature.py").write_text("VALUE = 2\n", encoding="utf-8")
        diff = capture_diff(workspace)
        return HarnessResult(diff=diff.patch, changed_files=diff.changed_files)


class _NoOpHarness:
    def propose_changes(
        self,
        objective: str,
        feedback,
        workspace: Worktree,
    ) -> HarnessResult:
        return HarnessResult(diff="", changed_files=[])


class _TimeoutHarness:
    def propose_changes(
        self,
        objective: str,
        feedback,
        workspace: Worktree,
    ) -> HarnessResult:
        from mergegate.harness.base import HarnessTimeoutError

        raise HarnessTimeoutError("agent exceeded its execution deadline")


class _ProtectedPathHarness:
    def propose_changes(
        self,
        objective: str,
        feedback,
        workspace: Worktree,
    ) -> HarnessResult:
        target = workspace.path / "app" / "auth" / "security.py"
        target.write_text("TOKEN = 'weakened'\n", encoding="utf-8")
        diff = capture_diff(workspace)
        return HarnessResult(diff=diff.patch, changed_files=diff.changed_files)


class _BlockingHarness:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()

    def propose_changes(
        self,
        objective: str,
        feedback,
        workspace: Worktree,
    ) -> HarnessResult:
        self.started.set()
        if not self.release.wait(timeout=20):
            raise RuntimeError("test did not release blocking harness")
        return HarnessResult(diff="", changed_files=[])


def _poll_run(client, run_id: str, terminal: set[str], timeout_s: float = 45) -> dict:
    deadline = time.time() + timeout_s
    body: dict = {}
    while time.time() < deadline:
        response = client.get(f"/api/runs/{run_id}")
        assert response.status_code == 200, response.text
        body = response.json()
        if body["status"] in terminal:
            return body
        time.sleep(0.1)
    pytest.fail(f"run did not reach {terminal}: {body!r}")


def test_two_attempt_failure_feedback_recovers_to_success(
    reliability_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _AdaptiveHarness()
    monkeypatch.setattr(nodes, "get_adapter", lambda *_args, **_kwargs: harness)
    run = _run(reliability_repo)
    contract = _contract(
        run.id, f'"{PY}" -c "from feature import VALUE; assert VALUE == 2"'
    )

    drive_run(_context(run, reliability_repo, contract, tmp_path))

    assert run.status == RunStatus.AWAITING_GATE
    assert run.current_attempt == 2
    assert run.attempts[0].verdict is not None
    assert run.attempts[0].verdict.passed is False
    assert run.attempts[1].verdict is not None
    assert run.attempts[1].verdict.passed is True
    assert harness.feedback[1].criterion == "task-tests"
    gates.approve_merge(run)
    assert run.status == RunStatus.SUCCESS


def test_invalid_command_records_exit_127_and_never_reports_success(
    reliability_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(nodes, "get_adapter", lambda *_args, **_kwargs: _NoOpHarness())
    run = _run(reliability_repo, max_attempts=2)
    contract = _contract(run.id, "mergegate-command-that-does-not-exist")

    drive_run(_context(run, reliability_repo, contract, tmp_path))

    assert run.status == RunStatus.NO_PROGRESS
    assert run.status != RunStatus.SUCCESS
    assert run.attempts[-1].verdict is not None
    assert run.attempts[-1].verdict.checks[0].exit_code == COMMAND_NOT_FOUND_EXIT_CODE
    assert run.undelivered_report is not None
    assert run.undelivered_report["delivered"] is False


def test_agent_timeout_is_truthfully_terminal_and_never_success(
    reliability_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        nodes, "get_adapter", lambda *_args, **_kwargs: _TimeoutHarness()
    )
    run = _run(reliability_repo)
    events: list[tuple[str, dict]] = []
    worktrees_root = tmp_path / "worktrees"
    contract = _contract(run.id, f'"{PY}" -c "raise SystemExit(1)"')

    drive_run(
        _context(
            run,
            reliability_repo,
            contract,
            tmp_path,
            events=events,
        )
    )

    assert run.status == RunStatus.TIMED_OUT
    assert run.status != RunStatus.SUCCESS
    assert run.undelivered_report is not None
    assert "deadline" in run.undelivered_report["reason"]
    terminal = next(payload for kind, payload in events if kind == "terminal")
    assert terminal["status"] == "TIMED_OUT"
    assert not any(worktrees_root.iterdir()), "timed-out attempt worktree leaked"


def test_human_rejection_at_final_gate_is_terminal_without_merge(
    reliability_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        nodes, "get_adapter", lambda *_args, **_kwargs: _SingleSuccessHarness()
    )
    run = _run(reliability_repo)
    contract = _contract(
        run.id, f'"{PY}" -c "from feature import VALUE; assert VALUE == 2"'
    )
    drive_run(_context(run, reliability_repo, contract, tmp_path))
    assert run.status == RunStatus.AWAITING_GATE

    gates.reject_merge(run, reason="operator rejected the patch")

    assert run.status == RunStatus.HUMAN_REJECTED
    assert run.ended_at is not None
    assert run.branch is None
    assert run.patch_ref is None


def test_manual_stop_cancels_active_run_and_records_terminal_evidence(
    client,
    workflow_id: str,
    demo_repo: Path,
    objective: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _BlockingHarness()
    created_worktrees: list[Worktree] = []
    create_worktree = nodes.create_worktree

    def track_worktree(*args, **kwargs) -> Worktree:
        worktree = create_worktree(*args, **kwargs)
        created_worktrees.append(worktree)
        return worktree

    monkeypatch.setattr(nodes, "create_worktree", track_worktree)
    monkeypatch.setattr(nodes, "get_adapter", lambda *_args, **_kwargs: harness)
    created = client.post(
        "/api/runs",
        json={
            "workflow_id": workflow_id,
            "objective": objective,
            "repo_ref": str(demo_repo),
            "provider": "scripted",
            "budgets": {
                "max_attempts": 3,
                "max_wall_clock_s": 300,
                "max_model_calls": 20,
            },
        },
    )
    run_id = created.json()["id"]
    client.post(f"/api/runs/{run_id}/criteria:generate", json={"mode": "hybrid"})
    client.post(f"/api/runs/{run_id}/criteria:approve")
    assert client.post(f"/api/runs/{run_id}:start").status_code == 202
    assert harness.started.wait(timeout=30), "harness did not start"

    stopped = client.post(f"/api/runs/{run_id}:stop")
    harness.release.set()

    assert stopped.status_code == 200, stopped.text
    assert stopped.json()["status"] == "CANCELLED"
    done = _poll_run(client, run_id, {"CANCELLED"})
    assert done["status"] == "CANCELLED"
    from mergegate.api.store import store

    record = store.get_run(run_id)
    assert record is not None
    assert record.thread is not None
    record.thread.join(timeout=30)
    assert not record.thread.is_alive(), "cancelled run driver did not stop"
    assert len(created_worktrees) == 1
    assert not created_worktrees[0].path.exists()
    registered = run_command(["git", "worktree", "list", "--porcelain"], cwd=demo_repo)
    assert str(created_worktrees[0].path) not in registered.stdout
    ledger = client.get(f"/api/runs/{run_id}/ledger").json()
    terminal = [entry for entry in ledger if entry["type"] == "terminal"]
    assert len(terminal) == 1
    assert terminal[0]["payload"]["status"] == "CANCELLED"
    assert terminal[0]["payload"]["reason"] == "stopped by operator"


def test_protected_file_change_is_blocked_with_named_offender(
    reliability_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        nodes, "get_adapter", lambda *_args, **_kwargs: _ProtectedPathHarness()
    )
    run = _run(reliability_repo)
    events: list[tuple[str, dict]] = []
    contract = _contract(run.id, f'"{PY}" -c "raise SystemExit(1)"')

    drive_run(
        _context(
            run,
            reliability_repo,
            contract,
            tmp_path,
            policy=Policy(protected_paths=["app/auth/**"]),
            events=events,
        )
    )

    assert run.status == RunStatus.POLICY_BLOCKED
    assert run.attempts[0].verdict is None
    blocked = next(payload for kind, payload in events if kind == "policy_block")
    assert blocked["path_or_pattern"] == "app/auth/security.py"


def test_attempt_budget_exhaustion_rolls_back_with_honest_report(
    reliability_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(nodes, "get_adapter", lambda *_args, **_kwargs: _NoOpHarness())
    run = _run(reliability_repo, max_attempts=1)
    contract = _contract(run.id, f'"{PY}" -c "raise SystemExit(1)"')

    drive_run(_context(run, reliability_repo, contract, tmp_path))

    assert run.status == RunStatus.EXHAUSTED
    assert run.current_attempt == 1
    assert run.undelivered_report is not None
    assert run.undelivered_report["reason"] == "attempt budget exhausted"
    assert run.undelivered_report["baseline_preserved"] is True
    assert not Path(run.attempts[0].worktree_path).exists()


def test_contradiction_requires_clarification_with_terminal_receipt(
    client,
    workflow_id: str,
    demo_repo: Path,
    contradictory_objective: str,
) -> None:
    created = client.post(
        "/api/runs",
        json={
            "workflow_id": workflow_id,
            "objective": contradictory_objective,
            "repo_ref": str(demo_repo),
            "provider": "scripted",
            "budgets": {
                "max_attempts": 3,
                "max_wall_clock_s": 300,
                "max_model_calls": 20,
            },
        },
    )
    run_id = created.json()["id"]
    client.post(f"/api/runs/{run_id}/criteria:generate", json={"mode": "hybrid"})
    client.post(f"/api/runs/{run_id}/criteria:approve")

    started = client.post(f"/api/runs/{run_id}:start")

    assert started.status_code == 200, started.text
    assert started.json()["status"] == "CLARIFICATION_REQUIRED"
    assert started.json()["current_attempt"] == 0
    ledger = client.get(f"/api/runs/{run_id}/ledger").json()
    terminal = [entry for entry in ledger if entry["type"] == "terminal"]
    assert len(terminal) == 1
    assert terminal[0]["payload"]["status"] == "CLARIFICATION_REQUIRED"
    assert terminal[0]["payload"]["clarification"]["conflicting_criteria"]


def _sse_request(run_id: str, last_event_id: int) -> Request:
    query = f"last_event_id={last_event_id}".encode()

    async def receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": f"/runs/{run_id}/events",
            "query_string": query,
            "headers": [],
        },
        receive,
    )


def test_mid_run_refresh_reconnects_after_persisted_sse_cursor() -> None:
    from mergegate.api.events import event_bus, stream_run_events

    run_id = f"run-refresh-{uuid4()}"
    event_bus.publish(run_id, "node_status", {"node": "planning", "status": "running"})
    event_bus.publish(run_id, "retry", {"attempt": 2, "reason": "acceptance failed"})

    async def reconnect() -> dict:
        response = await stream_run_events(run_id, _sse_request(run_id, 1))
        return cast(dict, await anext(aiter(response.body_iterator)))

    replayed = anyio.run(reconnect)

    assert replayed["id"] == "2"
    assert replayed["event"] == "retry"
    assert json.loads(replayed["data"])["attempt"] == 2


def test_backend_restart_limitation_is_explicit_not_silent(client) -> None:
    response = client.get("/api/runs/run-from-before-restart")

    assert response.status_code == 404
    assert "backend restart" in response.text.lower()
    limitation = (
        Path(__file__).resolve().parents[3] / "docs" / "reliability.md"
    ).read_text(encoding="utf-8")
    assert "backend restart" in limitation.lower()
    assert "process-local" in limitation.lower()
    assert "does not resume" in limitation.lower()
