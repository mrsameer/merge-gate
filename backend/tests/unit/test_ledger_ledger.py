"""Hash-chained ledger writer + JSONL mirror tests for T009.

Covers `ledger/ledger.py`'s `LedgerWriter`: each entry's `hash` is derived
from the previous entry's hash plus the canonical payload
(`H(prev_hash + canonical(payload))`, data-model.md), entries are mirrored to
both the SQLite `ledger` table (T008's schema) and an append-only JSONL file,
the chain resumes correctly across writer instances, and altering a stored
entry is detectable by recomputing its hash.
"""

import json

import pytest

from mergegate.ledger.ledger import LedgerWriter, canonical_json, compute_hash
from mergegate.ledger.store import connect
from mergegate.models.enums import LedgerEntryType


def _insert_run(conn, run_id: str = "r1") -> None:
    conn.execute(
        "INSERT INTO runs (id, workflow_id, objective, repo_ref, status, "
        "budgets, current_attempt, cost) VALUES (?, 'wf-1', 'obj', "
        "'repo@sha', 'running', '{}', 0, '{}')",
        (run_id,),
    )
    conn.commit()


def test_first_entry_chains_from_the_genesis_hash(tmp_path) -> None:
    conn = connect(":memory:")
    _insert_run(conn)
    writer = LedgerWriter(conn, "r1", tmp_path / "r1.jsonl")

    entry = writer.append(LedgerEntryType.OBJECTIVE, {"objective": "do the thing"})

    assert entry.seq == 1
    assert entry.prev_hash is None
    assert entry.hash == compute_hash(None, {"objective": "do the thing"})


def test_second_entry_chains_from_the_first_entrys_hash(tmp_path) -> None:
    conn = connect(":memory:")
    _insert_run(conn)
    writer = LedgerWriter(conn, "r1", tmp_path / "r1.jsonl")

    first = writer.append(LedgerEntryType.OBJECTIVE, {"objective": "do the thing"})
    second = writer.append(LedgerEntryType.PLAN, {"plan": "steps"})

    assert second.seq == 2
    assert second.prev_hash == first.hash
    assert second.hash == compute_hash(first.hash, {"plan": "steps"})
    assert second.hash != first.hash


def test_canonical_json_is_order_independent() -> None:
    assert canonical_json({"b": 1, "a": 2}) == canonical_json({"a": 2, "b": 1})


def test_canonical_json_survives_javascript_integral_float_serialization() -> None:
    assert canonical_json({"usd": 0.0, "nested": [1.0]}) == canonical_json(
        {"usd": 0, "nested": [1]}
    )


def test_compute_hash_changes_when_payload_changes() -> None:
    h1 = compute_hash("prev", {"a": 1})
    h2 = compute_hash("prev", {"a": 2})
    assert h1 != h2


def test_entries_are_persisted_to_the_sqlite_ledger_table(tmp_path) -> None:
    conn = connect(":memory:")
    _insert_run(conn)
    writer = LedgerWriter(conn, "r1", tmp_path / "r1.jsonl")
    entry = writer.append(LedgerEntryType.COMMAND, {"cmd": "pytest"})

    row = conn.execute(
        "SELECT seq, run_id, type, payload, prev_hash, hash FROM ledger "
        "WHERE run_id = 'r1' AND seq = 1"
    ).fetchone()

    assert row == (
        1,
        "r1",
        "command",
        canonical_json({"cmd": "pytest"}),
        None,
        entry.hash,
    )


def test_entries_are_mirrored_to_the_jsonl_file(tmp_path) -> None:
    conn = connect(":memory:")
    _insert_run(conn)
    jsonl_path = tmp_path / "nested" / "r1.jsonl"
    writer = LedgerWriter(conn, "r1", jsonl_path)

    writer.append(LedgerEntryType.OBJECTIVE, {"objective": "a"})
    writer.append(LedgerEntryType.PLAN, {"plan": "b"})

    lines = jsonl_path.read_text().splitlines()
    assert len(lines) == 2

    first_line = json.loads(lines[0])
    second_line = json.loads(lines[1])
    assert first_line["seq"] == 1
    assert first_line["type"] == "objective"
    assert first_line["prev_hash"] is None
    assert second_line["seq"] == 2
    assert second_line["prev_hash"] == first_line["hash"]


def test_writer_resumes_the_chain_from_an_existing_run(tmp_path) -> None:
    conn = connect(":memory:")
    _insert_run(conn)
    jsonl_path = tmp_path / "r1.jsonl"

    first_writer = LedgerWriter(conn, "r1", jsonl_path)
    first_entry = first_writer.append(LedgerEntryType.OBJECTIVE, {"objective": "a"})

    second_writer = LedgerWriter(conn, "r1", jsonl_path)
    second_entry = second_writer.append(LedgerEntryType.PLAN, {"plan": "b"})

    assert second_entry.seq == 2
    assert second_entry.prev_hash == first_entry.hash


def test_ledger_entries_across_two_runs_do_not_share_a_chain(tmp_path) -> None:
    conn = connect(":memory:")
    _insert_run(conn, "r1")
    _insert_run(conn, "r2")

    entry_r1 = LedgerWriter(conn, "r1", tmp_path / "r1.jsonl").append(
        LedgerEntryType.OBJECTIVE, {"objective": "a"}
    )
    entry_r2 = LedgerWriter(conn, "r2", tmp_path / "r2.jsonl").append(
        LedgerEntryType.OBJECTIVE, {"objective": "a"}
    )

    assert entry_r1.seq == 1
    assert entry_r2.seq == 1
    assert entry_r1.prev_hash is None
    assert entry_r2.prev_hash is None


def test_tampering_with_a_stored_entry_breaks_hash_recomputation(tmp_path) -> None:
    conn = connect(":memory:")
    _insert_run(conn)
    writer = LedgerWriter(conn, "r1", tmp_path / "r1.jsonl")
    entry = writer.append(LedgerEntryType.OBJECTIVE, {"objective": "original"})

    conn.execute(
        "UPDATE ledger SET payload = ? WHERE run_id = 'r1' AND seq = 1",
        (canonical_json({"objective": "tampered"}),),
    )
    conn.commit()

    row = conn.execute(
        "SELECT payload, prev_hash, hash FROM ledger WHERE run_id = 'r1' AND seq = 1"
    ).fetchone()
    stored_payload, stored_prev_hash, stored_hash = row

    recomputed = compute_hash(stored_prev_hash, json.loads(stored_payload))
    assert recomputed != stored_hash
    assert stored_hash == entry.hash


def test_append_requires_an_existing_run(tmp_path) -> None:
    conn = connect(":memory:")
    writer = LedgerWriter(conn, "missing-run", tmp_path / "r1.jsonl")

    with pytest.raises(Exception):
        writer.append(LedgerEntryType.OBJECTIVE, {"objective": "a"})
