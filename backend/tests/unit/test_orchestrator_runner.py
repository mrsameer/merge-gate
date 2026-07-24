"""Run state machine + SQLite-checkpointed graph execution tests for T013.

Encodes data-model.md's Run entity: the exhaustive terminal-state enum
(FR-025), the `running <-> awaiting_gate` / `running <-> paused` / `any ->
terminal` transition rules, and pause/resume/stop as operator-facing
transitions (FR-023) backed by a real LangGraph SQLite checkpointer so
`resume()` continues a Run from its last checkpoint instead of restarting it.
"""

import json

import pytest

from mergegate.models import Run, RunStatus
from mergegate.models.budget import Budget, CostAccounting
from mergegate.orchestrator.graph import GraphState, load_workflow_config
from mergegate.orchestrator.runner import (
    InvalidTransition,
    Runner,
    is_terminal,
    transition,
)

_LOOP_CONFIG: dict = {
    "id": "wf-loop",
    "name": "Default Loop",
    "nodes": [
        {"id": "input", "type": "Input", "name": "Objective"},
        {
            "id": "planning",
            "type": "Agent",
            "name": "Planning",
            "config": {"role": "planning"},
        },
        {
            "id": "execution",
            "type": "Agent",
            "name": "Execution",
            "config": {"role": "execution"},
        },
        {"id": "validation", "type": "Validator", "name": "Validation"},
        {"id": "success", "type": "Success", "name": "Success"},
        {"id": "stop", "type": "Stop", "name": "Stop"},
    ],
    "edges": [
        {"source": "input", "target": "planning"},
        {"source": "planning", "target": "execution"},
        {"source": "execution", "target": "validation"},
        {"source": "validation", "target": "success", "path": "success"},
        {"source": "validation", "target": "stop", "path": "failure"},
    ],
}


def _make_run(status: RunStatus = RunStatus.AWAITING_GATE) -> Run:
    return Run(
        id="run-1",
        workflow_id="wf-loop",
        objective="demo",
        repo_ref="main@deadbeef",
        status=status,
        budgets=Budget(max_attempts=5, max_wall_clock_s=600, max_model_calls=50),
        current_attempt=0,
        cost=CostAccounting(),
    )


def _make_runner(run: Run | None = None) -> Runner:
    workflow = load_workflow_config(json.dumps(_LOOP_CONFIG))
    return Runner(workflow, run or _make_run(), checkpoint_db=":memory:")


# --- terminal-state enum ------------------------------------------------


@pytest.mark.parametrize(
    "status",
    [
        RunStatus.SUCCESS,
        RunStatus.CLARIFICATION_REQUIRED,
        RunStatus.HUMAN_REJECTED,
        RunStatus.EXHAUSTED,
        RunStatus.NO_PROGRESS,
        RunStatus.TIMED_OUT,
        RunStatus.POLICY_BLOCKED,
        RunStatus.CANCELLED,
    ],
)
def test_is_terminal_true_for_every_terminal_state(status: RunStatus) -> None:
    assert is_terminal(status)


@pytest.mark.parametrize(
    "status", [RunStatus.RUNNING, RunStatus.PAUSED, RunStatus.AWAITING_GATE]
)
def test_is_terminal_false_for_non_terminal_states(status: RunStatus) -> None:
    assert not is_terminal(status)


# --- run state machine ---------------------------------------------------


def test_transition_running_to_awaiting_gate_and_back() -> None:
    run = _make_run(RunStatus.RUNNING)
    transition(run, RunStatus.AWAITING_GATE)
    assert run.status == RunStatus.AWAITING_GATE
    transition(run, RunStatus.RUNNING)
    assert run.status == RunStatus.RUNNING


def test_transition_running_to_paused_and_back() -> None:
    run = _make_run(RunStatus.RUNNING)
    transition(run, RunStatus.PAUSED)
    assert run.status == RunStatus.PAUSED
    transition(run, RunStatus.RUNNING)
    assert run.status == RunStatus.RUNNING


def test_transition_any_non_terminal_state_to_a_terminal_state() -> None:
    for start in (RunStatus.RUNNING, RunStatus.PAUSED, RunStatus.AWAITING_GATE):
        run = _make_run(start)
        transition(run, RunStatus.CANCELLED)
        assert run.status == RunStatus.CANCELLED


def test_transition_rejects_paused_to_awaiting_gate() -> None:
    run = _make_run(RunStatus.PAUSED)
    with pytest.raises(InvalidTransition):
        transition(run, RunStatus.AWAITING_GATE)
    assert run.status == RunStatus.PAUSED


def test_transition_rejects_leaving_a_terminal_state() -> None:
    run = _make_run(RunStatus.SUCCESS)
    with pytest.raises(InvalidTransition):
        transition(run, RunStatus.RUNNING)
    assert run.status == RunStatus.SUCCESS


def test_transition_sets_started_at_and_ended_at() -> None:
    run = _make_run(RunStatus.AWAITING_GATE)
    assert run.started_at is None
    transition(run, RunStatus.RUNNING)
    assert run.started_at is not None
    assert run.ended_at is None
    transition(run, RunStatus.CANCELLED)
    assert run.ended_at is not None


# --- pause/resume/stop transitions on the Runner --------------------------


def test_runner_start_transitions_awaiting_gate_to_running_then_terminal_free() -> None:
    runner = _make_runner()
    result = runner.start({"path": "success", "node_results": {}})
    assert runner.run.status == RunStatus.RUNNING
    assert result is not None
    assert result.get("node_results", {}).get("success") == "ran"


def test_runner_pause_stops_the_run_before_it_reaches_end() -> None:
    runner = _make_runner()

    def on_step(state: GraphState) -> None:
        if state.get("node_results", {}).get("planning") == "ran":
            runner.pause()

    result = runner.start({"path": "success", "node_results": {}}, on_step=on_step)
    assert runner.run.status == RunStatus.PAUSED
    assert result is not None
    assert result.get("node_results") == {"input": "ran", "planning": "ran"}
    assert "execution" not in result.get("node_results", {})


def test_runner_resume_continues_from_last_checkpoint_without_rerunning_nodes() -> None:
    runner = _make_runner()
    seen_planning_runs = []

    def pause_after_planning(state: GraphState) -> None:
        seen_planning_runs.append(state.get("node_results", {}).get("planning"))
        if state.get("node_results", {}).get("planning") == "ran":
            runner.pause()

    runner.start({"path": "success", "node_results": {}}, on_step=pause_after_planning)
    assert runner.run.status == RunStatus.PAUSED

    result = runner.resume()
    assert runner.run.status == RunStatus.RUNNING
    assert result is not None
    assert result.get("node_results", {}).get("success") == "ran"
    assert seen_planning_runs.count("ran") == 1


def test_runner_stop_cancels_a_running_run() -> None:
    runner = _make_runner()

    def on_step(state: GraphState) -> None:
        if state.get("node_results", {}).get("planning") == "ran":
            runner.stop()

    result = runner.start({"path": "success", "node_results": {}}, on_step=on_step)
    assert runner.run.status == RunStatus.CANCELLED
    assert result is not None
    assert "execution" not in result.get("node_results", {})


def test_runner_resume_requires_a_paused_run() -> None:
    runner = _make_runner()
    with pytest.raises(InvalidTransition):
        runner.resume()


def test_runner_exception_maps_to_a_safe_terminal_state_never_success() -> None:
    runner = _make_runner()

    def blow_up(state: GraphState) -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        runner.start({"path": "success", "node_results": {}}, on_step=blow_up)

    assert is_terminal(runner.run.status)
    assert runner.run.status != RunStatus.SUCCESS
