"""T054 — hash-chain verification fails closed on altered ledger history."""

from mergegate.ledger.ledger import LedgerWriter
from mergegate.ledger.store import connect
from mergegate.ledger.verify import verify_chain
from mergegate.models.enums import LedgerEntryType


def _ledger(tmp_path):
    conn = connect(":memory:")
    conn.execute(
        "INSERT INTO runs (id, workflow_id, objective, repo_ref, status, "
        "budgets, current_attempt, cost) VALUES "
        "('r1', 'wf-1', 'objective', 'repo', 'running', '{}', 0, '{}')"
    )
    conn.commit()
    writer = LedgerWriter(conn, "r1", tmp_path / "r1.jsonl")
    writer.append(LedgerEntryType.OBJECTIVE, {"objective": "ship receipts"})
    writer.append(LedgerEntryType.PLAN, {"plan": "implement and validate"})
    return writer.read_entries()


def test_verify_chain_accepts_an_intact_ordered_ledger(tmp_path) -> None:
    result = verify_chain(_ledger(tmp_path))

    assert result.valid is True
    assert result.broken_seq is None
    assert result.reason is None


def test_verify_chain_names_the_first_tampered_entry(tmp_path) -> None:
    entries = [entry.model_dump(mode="json") for entry in _ledger(tmp_path)]
    entries[0]["payload"]["objective"] = "tampered objective"

    result = verify_chain(entries)

    assert result.valid is False
    assert result.broken_seq == 1
    assert result.reason == "entry hash does not match its payload"


def test_verify_chain_rejects_reordered_or_forked_history(tmp_path) -> None:
    entries = [entry.model_dump(mode="json") for entry in _ledger(tmp_path)]
    entries[1]["prev_hash"] = "not-the-first-hash"

    result = verify_chain(entries)

    assert result.valid is False
    assert result.broken_seq == 2
    assert result.reason == "previous hash does not match"
