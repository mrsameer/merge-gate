"""Schema-valid evidence-bundle assembly from a completed run's ledger."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from jsonschema import Draft202012Validator

from mergegate.ledger.ledger import LedgerEntry
from mergegate.ledger.verify import verify_chain
from mergegate.models import Contract, Run
from mergegate.orchestrator.runner import is_terminal

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[4]
    / "specs"
    / "001-mergegate-control-plane"
    / "contracts"
    / "evidence-bundle.schema.json"
)


def _plain_entries(entries: Sequence[LedgerEntry | dict]) -> list[dict]:
    plain = [
        entry.model_dump(mode="json")
        if isinstance(entry, LedgerEntry)
        else LedgerEntry.model_validate(entry).model_dump(mode="json")
        for entry in entries
    ]
    for entry in plain:
        if entry["prev_hash"] is None:
            entry["prev_hash"] = ""
    return plain


def _payloads(entries: list[dict], entry_type: str) -> list[dict]:
    return [entry["payload"] for entry in entries if entry["type"] == entry_type]


def validate_bundle(bundle: dict) -> None:
    """Raise ``ValidationError`` when a bundle violates the public contract."""
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(bundle)


def assemble_evidence_bundle(
    *, run: Run, contract: Contract, entries: Sequence[LedgerEntry | dict]
) -> dict:
    """Assemble and validate the proof-carrying record for a completed run."""
    if not is_terminal(run.status):
        raise ValueError("evidence bundle is available only for a terminal run")
    if run.started_at is None or run.ended_at is None:
        raise ValueError("completed run is missing start or end time")
    if contract.frozen_hash is None:
        raise ValueError("completed run is missing a frozen contract")

    ledger = _plain_entries(entries)
    chain = verify_chain(ledger)
    if not chain.valid:
        raise ValueError(
            f"ledger verification failed at sequence {chain.broken_seq}: {chain.reason}"
        )

    plans = _payloads(ledger, "plan")
    harness = _payloads(ledger, "harness")
    verdicts = _payloads(ledger, "verdict")
    if not plans or not harness or not verdicts:
        raise ValueError("ledger is missing plan, harness, or verdict evidence")
    verdict = verdicts[-1]

    bundle = {
        "run_id": run.id,
        "terminal_state": run.status.value,
        "contract": {
            "mode": contract.mode.value,
            "criteria": [
                criterion.model_dump(mode="json") for criterion in contract.criteria
            ],
            "frozen_hash": contract.frozen_hash,
        },
        "plan": str(plans[-1].get("plan", "")),
        "diff": "\n".join(
            str(payload.get("diff", "")) for payload in harness if payload.get("diff")
        ),
        "commands": _payloads(ledger, "command"),
        "red_green_evidence": verdict["red_green_evidence"],
        "policy_results": _payloads(ledger, "policy"),
        "retries": _payloads(ledger, "retry"),
        "acceptance_hash": str(verdict["acceptance_hash"]),
        "acceptance_input": verdict.get("acceptance_input", {}),
        "cost": {
            "tokens": run.cost.tokens,
            "model_calls": run.cost.model_calls,
            "usd": run.cost.usd,
        },
        "time": {
            "started_at": run.started_at.isoformat(),
            "ended_at": run.ended_at.isoformat(),
            "wall_clock_s": (run.ended_at - run.started_at).total_seconds(),
        },
        "ledger": ledger,
    }
    validate_bundle(bundle)
    return bundle
