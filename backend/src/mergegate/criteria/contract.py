from __future__ import annotations

import hashlib
import json

from mergegate.models import Contract


def freeze_contract(contract: Contract) -> Contract:
    canonical = json.dumps(
        [c.model_dump(mode="json") for c in contract.criteria],
        sort_keys=True,
        separators=(",", ":"),
    )
    frozen_hash = hashlib.sha256(canonical.encode()).hexdigest()
    return contract.model_copy(
        update={"approved": True, "frozen_hash": frozen_hash},
    )
