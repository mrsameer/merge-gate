"""Run state machine + SQLite-checkpointed graph execution (T013,
data-model.md § Run, FR-023, FR-025).

`transition` enforces the Run state machine exactly as data-model.md defines
it: `running <-> awaiting_gate` (human gates), `running <-> paused`
(operator), and any non-terminal state to any of the eight terminal states
(FR-025) — terminal states are final. `Runner` drives one Run's compiled
workflow graph against a real LangGraph SQLite checkpointer, so `pause()`
merely flips the Run's status and `resume()` continues execution from the
last durably-saved checkpoint rather than re-running earlier nodes.

Deciding *what* a node does, and detecting budget exhaustion or no-progress,
is the concern of later tasks (T027, T040, T041); this module only owns the
generic status machine and the checkpointed execution loop that those tasks
build on.
"""

import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite import SqliteSaver

from mergegate.criteria.consistency import ConsistencyIssue
from mergegate.models import ClarificationRequest, Run, RunStatus, Workflow
from mergegate.models.policy import PolicyViolation
from mergegate.orchestrator.graph import GraphState, build_graph

_NON_TERMINAL = frozenset(
    {RunStatus.RUNNING, RunStatus.PAUSED, RunStatus.AWAITING_GATE}
)
_TERMINAL_STATES = frozenset(RunStatus) - _NON_TERMINAL

_ALLOWED_TRANSITIONS: dict[RunStatus, frozenset[RunStatus]] = {
    RunStatus.RUNNING: frozenset({RunStatus.PAUSED, RunStatus.AWAITING_GATE})
    | _TERMINAL_STATES,
    RunStatus.AWAITING_GATE: frozenset({RunStatus.RUNNING}) | _TERMINAL_STATES,
    RunStatus.PAUSED: frozenset({RunStatus.RUNNING}) | _TERMINAL_STATES,
}


class InvalidTransition(RuntimeError):
    """Raised when a Run status change violates data-model.md's Run state machine."""


def is_terminal(status: RunStatus) -> bool:
    """Whether `status` is one of the eight terminal states (FR-025)."""
    return status not in _NON_TERMINAL


def transition(run: Run, to: RunStatus) -> None:
    """Move `run` to status `to`, enforcing the Run state machine.

    Valid moves: `running -> awaiting_gate`, `awaiting_gate -> running`,
    `running -> paused`, `paused -> running`, and any non-terminal state to
    any terminal state. A terminal state has no outgoing transitions —
    Principle IV requires the terminal-state enum to be exhaustive and
    exceptions to never resolve to `SUCCESS`, so once a Run is terminal it
    stays terminal.
    """
    allowed = _ALLOWED_TRANSITIONS.get(run.status, frozenset())
    if to not in allowed:
        raise InvalidTransition(f"cannot move Run from {run.status} to {to}")

    run.status = to
    now = datetime.now(UTC)
    if run.started_at is None and to == RunStatus.RUNNING:
        run.started_at = now
    if is_terminal(to):
        run.ended_at = now


def require_clarification(
    run: Run,
    issue: ConsistencyIssue,
    on_terminal: Callable[[dict], None] | None = None,
) -> ClarificationRequest:
    """Halt ``run`` with a structured request before any attempt is created.

    The caller must invoke this at the pre-execution boundary.  Keeping the
    terminal transition here makes the zero-attempt invariant explicit and
    gives REST and SSE consumers the same payload.
    """

    if run.current_attempt != 0 or run.attempts:
        raise InvalidTransition(
            "clarification must be requested before an execution attempt"
        )
    clarification = ClarificationRequest(
        reason=issue.reason,
        conflicting_criteria=list(issue.conflicting_criteria),
    )
    run.clarification = clarification
    transition(run, RunStatus.CLARIFICATION_REQUIRED)
    if on_terminal is not None:
        on_terminal(
            {
                "status": RunStatus.CLARIFICATION_REQUIRED.value,
                "clarification": clarification.model_dump(mode="json"),
                "current_attempt": 0,
            }
        )
    return clarification


def block_for_policy(run: Run, violation: PolicyViolation) -> dict:
    """Move a run to ``POLICY_BLOCKED`` and return truthful event evidence."""
    transition(run, RunStatus.POLICY_BLOCKED)
    return {
        "kind": violation.kind,
        "path_or_pattern": violation.offender,
        "rule": violation.rule,
        "path": violation.path,
        "message": violation.message,
    }


class Runner:
    """Executes one Run's workflow graph against a durable SQLite checkpoint,
    exposing the pause/resume/stop operator controls (FR-023).
    """

    def __init__(
        self,
        workflow: Workflow,
        run: Run,
        checkpoint_db: str | Path = ":memory:",
    ) -> None:
        self._conn = sqlite3.connect(str(checkpoint_db), check_same_thread=False)
        self._checkpointer = SqliteSaver(self._conn)
        self._graph = build_graph(workflow, checkpointer=self._checkpointer)
        self._run = run

    @property
    def run(self) -> Run:
        return self._run

    def close(self) -> None:
        """Release the underlying SQLite connection."""
        self._conn.close()

    def start(
        self,
        initial_state: GraphState,
        on_step: Callable[[GraphState], None] | None = None,
    ) -> GraphState | None:
        """Begin execution from `initial_state` (FR-023's `:start`)."""
        transition(self._run, RunStatus.RUNNING)
        return self._stream(initial_state, on_step)

    def resume(
        self, on_step: Callable[[GraphState], None] | None = None
    ) -> GraphState | None:
        """Continue a paused Run from its last SQLite checkpoint (`:resume`).

        Unlike `transition`, which also allows `awaiting_gate -> running`
        (a human gate approval — T029's concern), `resume` specifically
        requires a `paused` Run: only a paused Run has a mid-execution
        checkpoint to continue from.
        """
        if self._run.status != RunStatus.PAUSED:
            raise InvalidTransition(f"cannot resume a Run in status {self._run.status}")
        transition(self._run, RunStatus.RUNNING)
        return self._stream(None, on_step)

    def pause(self) -> None:
        """Mark the Run paused; the in-flight `_stream` loop stops after its
        current step rather than being interrupted mid-node.
        """
        transition(self._run, RunStatus.PAUSED)

    def stop(self) -> None:
        """Cancel the Run (`:stop`)."""
        transition(self._run, RunStatus.CANCELLED)

    @property
    def _config(self) -> RunnableConfig:
        return RunnableConfig(configurable={"thread_id": self._run.id})

    def _stream(
        self,
        input_state: GraphState | None,
        on_step: Callable[[GraphState], None] | None,
    ) -> GraphState | None:
        last: GraphState | None = None
        try:
            for value in self._graph.stream(
                input_state, self._config, stream_mode="values"
            ):
                state = cast(GraphState, value)
                last = state
                if on_step is not None:
                    on_step(state)
                if self._run.status != RunStatus.RUNNING:
                    break
        except Exception:
            if not is_terminal(self._run.status):
                transition(self._run, RunStatus.CANCELLED)
            raise
        return last
