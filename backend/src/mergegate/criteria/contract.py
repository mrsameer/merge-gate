"""Draft editing and deterministic approval for MergeGate contracts."""

from __future__ import annotations

import hashlib
import json
from typing import Iterable

from mergegate.models import Contract, Criterion


class ContractStateError(ValueError):
    """An attempted contract transition is not allowed."""


def edit_draft(contract: Contract, criteria: Iterable[Criterion]) -> Contract:
    """Return a revised draft. Approved contracts are immutable acceptance targets."""

    if contract.approved:
        raise ContractStateError("an approved contract cannot be edited; create a new draft")
    return Contract(
        id=contract.id,
        run_id=contract.run_id,
        mode=contract.mode,
        criteria=tuple(criteria),
    )


def approve_contract(contract: Contract) -> Contract:
    """Approve and freeze a draft, or idempotently return a valid frozen contract."""

    if contract.approved:
        if not verify_frozen_contract(contract):
            raise ContractStateError("approved contract content does not match its frozen_hash")
        return contract
    return Contract(
        id=contract.id,
        run_id=contract.run_id,
        mode=contract.mode,
        criteria=contract.criteria,
        approved=True,
        frozen_hash=contract_hash(contract),
    )


def verify_frozen_contract(contract: Contract) -> bool:
    """Return whether an approved contract still matches its recorded acceptance target."""

    return bool(contract.approved and contract.frozen_hash == contract_hash(contract))


def contract_hash(contract: Contract) -> str:
    """Hash only stable acceptance semantics, never run IDs or timestamps."""

    criteria = sorted(contract.criteria, key=lambda criterion: (criterion.priority, criterion.id))
    payload = {
        "mode": contract.mode,
        "criteria": [criterion.model_dump(mode="json") for criterion in criteria],
    }
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
