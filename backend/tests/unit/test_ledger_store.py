"""SQLite schema + connection/init tests for T008.

Covers `ledger/store.py`'s two responsibilities: opening a connection that
always has the `runs`, `attempts`, and `ledger` tables present (creating them
on first use, leaving them untouched on reuse) and enforcing the shape those
tables need for T009's hash-chained writer — foreign keys from attempts/ledger
back to runs, and a unique `(run_id, seq)` per ledger entry so the chain can't
fork.
"""

import sqlite3

import pytest

from mergegate.ledger.store import connect


def _table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    return {row[0] for row in rows}


def _column_names(conn: sqlite3.Connection, table: str) -> list[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return [row[1] for row in rows]


def test_connect_creates_runs_attempts_and_ledger_tables() -> None:
    conn = connect(":memory:")
    assert {"runs", "attempts", "ledger"} <= _table_names(conn)


def test_connect_is_idempotent_on_an_existing_database(tmp_path) -> None:
    db_path = tmp_path / "mergegate.db"
    first = connect(db_path)
    first.execute(
        "INSERT INTO runs (id, workflow_id, objective, repo_ref, status, "
        "budgets, current_attempt, cost) VALUES "
        "('r1', 'wf-1', 'obj', 'repo@sha', 'running', '{}', 0, '{}')"
    )
    first.commit()
    first.close()

    second = connect(db_path)
    row = second.execute("SELECT id FROM runs WHERE id = 'r1'").fetchone()
    assert row is not None
    assert {"runs", "attempts", "ledger"} <= _table_names(second)


def test_runs_table_has_expected_columns() -> None:
    conn = connect(":memory:")
    columns = _column_names(conn, "runs")
    assert columns == [
        "id",
        "workflow_id",
        "objective",
        "repo_ref",
        "status",
        "budgets",
        "current_attempt",
        "cost",
        "started_at",
        "ended_at",
    ]


def test_attempts_table_has_expected_columns() -> None:
    conn = connect(":memory:")
    columns = _column_names(conn, "attempts")
    assert columns == [
        "id",
        "run_id",
        "idx",
        "worktree_path",
        "branch",
        "diff",
        "changed_files",
        "harness_log",
        "verdict",
        "failure_signature",
        "feedback",
    ]


def test_ledger_table_has_expected_columns() -> None:
    conn = connect(":memory:")
    columns = _column_names(conn, "ledger")
    assert columns == [
        "seq",
        "run_id",
        "ts",
        "type",
        "payload",
        "prev_hash",
        "hash",
    ]


def _insert_run(conn: sqlite3.Connection, run_id: str = "r1") -> None:
    conn.execute(
        "INSERT INTO runs (id, workflow_id, objective, repo_ref, status, "
        "budgets, current_attempt, cost) VALUES (?, 'wf-1', 'obj', "
        "'repo@sha', 'running', '{}', 0, '{}')",
        (run_id,),
    )


def test_attempts_foreign_key_to_runs_is_enforced() -> None:
    conn = connect(":memory:")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO attempts (id, run_id, idx, worktree_path, branch, "
            "diff, changed_files, harness_log) VALUES "
            "('a1', 'missing-run', 1, '/tmp/wt', 'attempt-1', '', '[]', '')"
        )


def test_attempts_insert_succeeds_for_an_existing_run() -> None:
    conn = connect(":memory:")
    _insert_run(conn)
    conn.execute(
        "INSERT INTO attempts (id, run_id, idx, worktree_path, branch, "
        "diff, changed_files, harness_log) VALUES "
        "('a1', 'r1', 1, '/tmp/wt', 'attempt-1', '', '[]', '')"
    )
    conn.commit()
    row = conn.execute("SELECT run_id FROM attempts WHERE id = 'a1'").fetchone()
    assert row[0] == "r1"


def test_ledger_foreign_key_to_runs_is_enforced() -> None:
    conn = connect(":memory:")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO ledger (seq, run_id, ts, type, payload, hash) "
            "VALUES (1, 'missing-run', '2026-01-01T00:00:00Z', 'objective', "
            "'{}', 'h1')"
        )


def test_ledger_rejects_duplicate_seq_for_the_same_run() -> None:
    conn = connect(":memory:")
    _insert_run(conn)
    conn.execute(
        "INSERT INTO ledger (seq, run_id, ts, type, payload, hash) "
        "VALUES (1, 'r1', '2026-01-01T00:00:00Z', 'objective', '{}', 'h1')"
    )
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO ledger (seq, run_id, ts, type, payload, hash) "
            "VALUES (1, 'r1', '2026-01-01T00:00:01Z', 'plan', '{}', 'h2')"
        )
