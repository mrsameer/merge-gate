"""Unit tests for run-level cost accounting (T074, FR-022).

Covers the pure aggregation of harness usage into a `CostAccounting` and the
single persistence edge that records a cost snapshot on the hash-chained
ledger. Aggregation is tested without any I/O; persistence uses a real
in-memory ledger so the recorded payload is asserted against actual stored
state (Principle II/III).
"""

from __future__ import annotations

import json

from mergegate.harness.base import HarnessResult
from mergegate.ledger.ledger import LedgerWriter, canonical_json
from mergegate.ledger.store import connect
from mergegate.models.budget import CostAccounting
from mergegate.models.enums import LedgerEntryType
from mergegate.orchestrator import cost


def _insert_run(conn, run_id: str = "r1") -> None:
    conn.execute(
        "INSERT INTO runs (id, workflow_id, objective, repo_ref, status, "
        "budgets, current_attempt, cost) VALUES (?, 'wf-1', 'obj', "
        "'repo@sha', 'running', '{}', 0, '{}')",
        (run_id,),
    )
    conn.commit()


def test_aggregate_empty_sequence_is_a_zero_accounting() -> None:
    total = cost.aggregate_cost([])

    assert total.tokens == 0
    assert total.model_calls == 0
    assert total.usd == 0.0
    assert total.wall_clock_s == 0.0


def test_aggregate_folds_multiple_calls() -> None:
    results = [
        HarnessResult(diff="", tokens=100, model_calls=1, usd=0.5),
        HarnessResult(diff="", tokens=250, model_calls=2, usd=1.25),
        HarnessResult(diff="", tokens=0, model_calls=0, usd=0.0),
    ]

    total = cost.aggregate_cost(results, wall_clock_s=4.5)

    assert total.tokens == 350
    assert total.model_calls == 3
    assert total.usd == 1.75
    assert total.wall_clock_s == 4.5


def test_add_result_accumulates_immutably() -> None:
    start = CostAccounting(tokens=10, model_calls=1, usd=0.2, wall_clock_s=1.0)
    result = HarnessResult(diff="", tokens=90, model_calls=1, usd=0.3)

    updated = cost.add_result(start, result, wall_clock_s=2.5)

    # Original is untouched; the update is a fresh accounting.
    assert start.tokens == 10 and start.model_calls == 1
    assert updated.tokens == 100
    assert updated.model_calls == 2
    assert updated.usd == 0.5
    assert updated.wall_clock_s == 3.5


def test_record_cost_persists_a_snapshot_to_the_ledger(tmp_path) -> None:
    conn = connect(":memory:")
    _insert_run(conn)
    writer = LedgerWriter(conn, "r1", tmp_path / "r1.jsonl")

    snapshot = CostAccounting(tokens=350, model_calls=3, usd=1.75, wall_clock_s=4.5)
    entry = cost.record_cost(writer, snapshot)

    assert entry.type == LedgerEntryType.HARNESS
    assert entry.payload == {
        "tokens": 350,
        "model_calls": 3,
        "usd": 1.75,
        "wall_clock_s": 4.5,
    }

    row = conn.execute(
        "SELECT type, payload FROM ledger WHERE run_id = 'r1' AND seq = 1"
    ).fetchone()
    assert row[0] == "harness"
    assert json.loads(row[1]) == cost.cost_payload(snapshot)
    assert row[1] == canonical_json(cost.cost_payload(snapshot))


def test_record_cost_chains_successive_snapshots(tmp_path) -> None:
    conn = connect(":memory:")
    _insert_run(conn)
    writer = LedgerWriter(conn, "r1", tmp_path / "r1.jsonl")

    running = CostAccounting()
    for result in (
        HarnessResult(diff="", tokens=100, model_calls=1, usd=0.5),
        HarnessResult(diff="", tokens=50, model_calls=1, usd=0.25),
    ):
        running = cost.add_result(running, result, wall_clock_s=1.0)
        cost.record_cost(writer, running)

    rows = conn.execute(
        "SELECT seq, prev_hash, hash FROM ledger WHERE run_id = 'r1' ORDER BY seq"
    ).fetchall()
    assert len(rows) == 2
    # Second snapshot chains from the first (append-only, hash-linked).
    assert rows[1][1] == rows[0][2]

    latest = json.loads(
        conn.execute(
            "SELECT payload FROM ledger WHERE run_id = 'r1' AND seq = 2"
        ).fetchone()[0]
    )
    assert latest == {
        "tokens": 150,
        "model_calls": 2,
        "usd": 0.75,
        "wall_clock_s": 2.0,
    }
