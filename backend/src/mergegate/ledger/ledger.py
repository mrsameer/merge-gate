"""Append-only, hash-chained ledger writer + JSONL mirror (Principle III, FR-019).

Each entry's `hash` is derived from the previous entry's hash and its own
payload (`H(prev_hash + canonical(payload))`, data-model.md's `LedgerEntry`),
so altering any prior entry breaks the chain. Writes are mirrored to the
SQLite `ledger` table from T008's `store.py` (query/timeline) and to an
append-only JSONL file (portable, diff-friendly), per research.md's storage
decision.
"""

import hashlib
import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from mergegate.models.enums import LedgerEntryType

_GENESIS_HASH = ""


class LedgerEntry(BaseModel):
    """One append-only, hash-chained ledger record (data-model.md)."""

    seq: int
    run_id: str
    ts: str
    type: LedgerEntryType
    payload: dict
    prev_hash: str | None
    hash: str


def _normalize_json_numbers(value):
    """Keep canonical hashes stable across Python/JavaScript JSON round-trips."""
    if isinstance(value, dict):
        return {key: _normalize_json_numbers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_json_numbers(item) for item in value]
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def canonical_json(payload: dict) -> str:
    """Deterministic JSON serialization used as hash-chain input."""
    return json.dumps(
        _normalize_json_numbers(payload),
        sort_keys=True,
        separators=(",", ":"),
    )


def compute_hash(prev_hash: str | None, payload: dict) -> str:
    """`H(prev_hash + canonical(payload))`, per data-model.md's `LedgerEntry.hash`."""
    digest_input = (prev_hash or _GENESIS_HASH) + canonical_json(payload)
    return hashlib.sha256(digest_input.encode("utf-8")).hexdigest()


class LedgerWriter:
    """Appends hash-chained ledger entries for one run.

    Resumes the chain from the run's last SQLite row on construction, so a
    new writer instance continues correctly after a restart.
    """

    def __init__(
        self, conn: sqlite3.Connection, run_id: str, jsonl_path: str | Path
    ) -> None:
        self._conn = conn
        self._run_id = run_id
        self._jsonl_path = Path(jsonl_path)
        self._jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._seq, self._prev_hash = self._load_tip()

    def _load_tip(self) -> tuple[int, str | None]:
        row = self._conn.execute(
            "SELECT seq, hash FROM ledger WHERE run_id = ? ORDER BY seq DESC LIMIT 1",
            (self._run_id,),
        ).fetchone()
        if row is None:
            return 0, None
        return row[0], row[1]

    def append(self, entry_type: LedgerEntryType, payload: dict) -> LedgerEntry:
        """Append one event, chaining it to the previous entry's hash."""
        with self._lock:
            entry = LedgerEntry(
                seq=self._seq + 1,
                run_id=self._run_id,
                ts=datetime.now(UTC).isoformat(),
                type=entry_type,
                payload=payload,
                prev_hash=self._prev_hash,
                hash=compute_hash(self._prev_hash, payload),
            )
            self._write_sqlite(entry)
            self._write_jsonl(entry)
            self._seq = entry.seq
            self._prev_hash = entry.hash
            return entry

    def read_entries(self) -> list[LedgerEntry]:
        """Return this run's durable ledger in canonical sequence order."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT seq, run_id, ts, type, payload, prev_hash, hash "
                "FROM ledger WHERE run_id = ? ORDER BY seq",
                (self._run_id,),
            ).fetchall()
        return [
            LedgerEntry(
                seq=row[0],
                run_id=row[1],
                ts=row[2],
                type=row[3],
                payload=json.loads(row[4]),
                prev_hash=row[5],
                hash=row[6],
            )
            for row in rows
        ]

    def _write_sqlite(self, entry: LedgerEntry) -> None:
        self._conn.execute(
            "INSERT INTO ledger (seq, run_id, ts, type, payload, prev_hash, hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                entry.seq,
                entry.run_id,
                entry.ts,
                entry.type.value,
                canonical_json(entry.payload),
                entry.prev_hash,
                entry.hash,
            ),
        )
        self._conn.commit()

    def _write_jsonl(self, entry: LedgerEntry) -> None:
        with self._jsonl_path.open("a", encoding="utf-8") as f:
            f.write(entry.model_dump_json() + "\n")
