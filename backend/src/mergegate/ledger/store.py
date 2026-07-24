"""SQLite schema and connection/init for the ledger store (runs, attempts,
ledger tables).

This module only owns the schema and connection lifecycle. Writing entries
with `prev_hash` chaining is T009's `ledger/ledger.py`.
"""

import sqlite3
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    objective TEXT NOT NULL,
    repo_ref TEXT NOT NULL,
    status TEXT NOT NULL,
    budgets TEXT NOT NULL,
    current_attempt INTEGER NOT NULL,
    cost TEXT NOT NULL,
    started_at TEXT,
    ended_at TEXT
);

CREATE TABLE IF NOT EXISTS attempts (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs (id),
    idx INTEGER NOT NULL,
    worktree_path TEXT NOT NULL,
    branch TEXT NOT NULL,
    diff TEXT NOT NULL,
    changed_files TEXT NOT NULL,
    harness_log TEXT NOT NULL,
    verdict TEXT,
    failure_signature TEXT,
    feedback TEXT
);

CREATE TABLE IF NOT EXISTS ledger (
    seq INTEGER NOT NULL,
    run_id TEXT NOT NULL REFERENCES runs (id),
    ts TEXT NOT NULL,
    type TEXT NOT NULL,
    payload TEXT NOT NULL,
    prev_hash TEXT,
    hash TEXT NOT NULL,
    PRIMARY KEY (run_id, seq)
);
"""


def init_schema(conn: sqlite3.Connection) -> None:
    """Create the runs/attempts/ledger tables if they don't already exist."""
    conn.executescript(_SCHEMA)
    conn.commit()


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open a SQLite connection at `db_path`, ensuring the schema exists.

    `db_path` may be `:memory:` for an ephemeral database. Foreign keys are
    enabled so attempts/ledger rows are constrained to an existing run.
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    init_schema(conn)
    return conn
