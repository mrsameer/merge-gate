"""In-process, thread-safe store for workflows, runs, and their contracts.

Persistence beyond the process lifetime is out of scope for US1 (the durable
ledger is a later story); this store keeps just enough shared state for the
Runs API and the background run driver to cooperate: the created `Workflow`s,
each `Run` plus its draft/frozen `Contract`, and the driver thread handle.

A single re-entrant lock guards the dictionaries so the polling `GET` handlers
and the background `drive_run` thread never observe a half-inserted record.
The mutable `Run` object itself is shared by reference with the driver, which
mutates it in place — that is intentional and how status/cost/attempt updates
become visible to `GET /runs/{id}`.
"""

from __future__ import annotations

import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path

from mergegate.ledger.ledger import LedgerWriter
from mergegate.ledger.store import connect
from mergegate.models import Contract, Run, Workflow
from mergegate.models.enums import LedgerEntryType


@dataclass
class RunRecord:
    """A run plus the workflow it belongs to and its (draft or frozen) contract."""

    run: Run
    workflow: Workflow
    contract: Contract | None = None
    thread: threading.Thread | None = field(default=None, repr=False)
    ledger: LedgerWriter | None = field(default=None, repr=False)


class Store:
    """Thread-safe in-memory registry of workflows and runs."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._workflows: dict[str, Workflow] = {}
        self._runs: dict[str, RunRecord] = {}
        self._ledger_root = Path(tempfile.mkdtemp(prefix="mergegate-ledger-"))

    def add_workflow(self, workflow: Workflow) -> None:
        with self._lock:
            self._workflows[workflow.id] = workflow

    def get_workflow(self, workflow_id: str) -> Workflow | None:
        with self._lock:
            return self._workflows.get(workflow_id)

    def add_run(self, run: Run, workflow: Workflow) -> RunRecord:
        with self._lock:
            ledger_conn = connect(
                self._ledger_root / f"{run.id}.sqlite3",
                check_same_thread=False,
            )
            ledger_conn.execute(
                "INSERT INTO runs (id, workflow_id, objective, repo_ref, status, "
                "budgets, current_attempt, cost, started_at, ended_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run.id,
                    run.workflow_id,
                    run.objective,
                    run.repo_ref,
                    run.status.value,
                    run.budgets.model_dump_json(),
                    run.current_attempt,
                    run.cost.model_dump_json(),
                    None,
                    None,
                ),
            )
            ledger_conn.commit()
            ledger = LedgerWriter(
                ledger_conn,
                run.id,
                self._ledger_root / f"{run.id}.jsonl",
            )
            ledger.append(
                LedgerEntryType.OBJECTIVE,
                {"objective": run.objective, "repo_ref": run.repo_ref},
            )
            record = RunRecord(run=run, workflow=workflow, ledger=ledger)
            self._runs[run.id] = record
        return record

    def get_run(self, run_id: str) -> RunRecord | None:
        with self._lock:
            return self._runs.get(run_id)


# Process-wide store instance shared by the API routers.
store = Store()
