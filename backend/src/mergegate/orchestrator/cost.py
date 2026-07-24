from __future__ import annotations

from mergegate.harness.base import HarnessResult
from mergegate.models import CostAccounting


def accumulate_cost(
    cost: CostAccounting, harness_result: HarnessResult
) -> CostAccounting:
    return CostAccounting(
        model_calls=cost.model_calls + harness_result.model_calls,
        tokens=cost.tokens + harness_result.tokens,
        usd=cost.usd + harness_result.usd,
        wall_clock_s=cost.wall_clock_s,
    )
