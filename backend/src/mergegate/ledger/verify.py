"""Deterministic verification for append-only, hash-chained run ledgers."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel

from mergegate.ledger.ledger import LedgerEntry, compute_hash


class ChainVerification(BaseModel):
    """Result of verifying one ordered ledger."""

    valid: bool
    broken_seq: int | None = None
    reason: str | None = None


def _entry(value: LedgerEntry | dict) -> LedgerEntry:
    if isinstance(value, LedgerEntry):
        return value
    return LedgerEntry.model_validate(value)


def verify_chain(entries: Sequence[LedgerEntry | dict]) -> ChainVerification:
    """Verify sequence continuity, links, and every stored payload hash."""
    previous_hash: str | None = None
    for expected_seq, value in enumerate(entries, start=1):
        try:
            entry = _entry(value)
        except (TypeError, ValueError):
            return ChainVerification(
                valid=False,
                broken_seq=expected_seq,
                reason="entry is malformed",
            )
        if entry.seq != expected_seq:
            return ChainVerification(
                valid=False,
                broken_seq=entry.seq,
                reason="sequence is not contiguous",
            )
        entry_prev_hash = entry.prev_hash or None
        if entry_prev_hash != previous_hash:
            return ChainVerification(
                valid=False,
                broken_seq=entry.seq,
                reason="previous hash does not match",
            )
        if entry.hash != compute_hash(entry_prev_hash, entry.payload):
            return ChainVerification(
                valid=False,
                broken_seq=entry.seq,
                reason="entry hash does not match its payload",
            )
        previous_hash = entry.hash
    return ChainVerification(valid=True)
