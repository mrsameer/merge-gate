"""T074 — Run-level cost accounting (FR-022).

The harness reports its usage per `propose_changes` call as a `HarnessResult`
(tokens / model-calls / USD); the orchestrator measures how long that call took
(wall-clock). This module is the pure, testable seam that folds those per-call
figures into a Run's `CostAccounting` and records each update on the
append-only ledger, so "what the run cost" is recoverable from recorded state
rather than recomputed.

The aggregation functions are pure (no I/O); `record_cost` is the single
persistence edge, kept separate so the fold can be unit-tested without a
database and wired into the run driver (`nodes.py`) at the edges.
"""

from __future__ import annotations

from collections.abc import Iterable

from mergegate.harness.base import HarnessResult
from mergegate.ledger.ledger import LedgerEntry, LedgerWriter
from mergegate.models.budget import CostAccounting
from mergegate.models.enums import LedgerEntryType


def add_result(
    cost: CostAccounting, result: HarnessResult, wall_clock_s: float = 0.0
) -> CostAccounting:
    """Return a new `CostAccounting` with one harness result folded in.

    Immutable by design — the caller rebinds ``run.cost`` to the returned
    value, so a concurrently polling reader always sees a whole, consistent
    accounting rather than a half-updated one.

    Args:
        cost: The running total so far.
        result: One `propose_changes` call's reported usage.
        wall_clock_s: Wall-clock seconds that call took (measured by the
            orchestrator; the harness result does not carry timing).
    """
    return CostAccounting(
        tokens=cost.tokens + result.tokens,
        model_calls=cost.model_calls + result.model_calls,
        usd=cost.usd + result.usd,
        wall_clock_s=cost.wall_clock_s + wall_clock_s,
    )


def aggregate_cost(
    results: Iterable[HarnessResult], wall_clock_s: float = 0.0
) -> CostAccounting:
    """Fold a sequence of harness results into a single `CostAccounting`.

    A pure reduction over `results` starting from an empty accounting. The
    optional `wall_clock_s` is the total wall-clock to attribute to the
    aggregate (per-call timing is not part of `HarnessResult`).
    """
    total = CostAccounting(wall_clock_s=wall_clock_s)
    for result in results:
        total = CostAccounting(
            tokens=total.tokens + result.tokens,
            model_calls=total.model_calls + result.model_calls,
            usd=total.usd + result.usd,
            wall_clock_s=total.wall_clock_s,
        )
    return total


def cost_payload(cost: CostAccounting) -> dict:
    """The canonical ledger payload for a cost snapshot."""
    return {
        "tokens": cost.tokens,
        "model_calls": cost.model_calls,
        "usd": cost.usd,
        "wall_clock_s": cost.wall_clock_s,
    }


def record_cost(writer: LedgerWriter, cost: CostAccounting) -> LedgerEntry:
    """Persist a cost snapshot to the hash-chained ledger (FR-022, FR-019).

    Recorded under `LedgerEntryType.HARNESS`, since a run's spend originates
    entirely from harness invocations; the payload is the full accumulated
    accounting so the ledger carries a recoverable running total.
    """
    return writer.append(LedgerEntryType.HARNESS, cost_payload(cost))
