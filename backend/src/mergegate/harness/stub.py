from __future__ import annotations

from pathlib import Path
from typing import Any

from mergegate.harness.base import HarnessAdapter, HarnessResult


class StubHarnessAdapter(HarnessAdapter):
    """Deterministic harness for tests and local demo — no model calls."""

    def propose_changes(
        self,
        *,
        objective: str,
        feedback: dict[str, Any] | None,
        workspace: str,
    ) -> HarnessResult:
        orders_router = Path(workspace) / "app" / "orders" / "router.py"
        content = orders_router.read_text(encoding="utf-8")
        if "Idempotency-Key" not in content:
            replacement = (
                '"""Idempotent order creation\n\n'
                "    Requires Idempotency-Key header.\n"
                '    """\n\n'
                "    # Baseline stub"
            )
            updated = content.replace('"""Baseline stub', replacement)
            orders_router.write_text(updated, encoding="utf-8")
            return HarnessResult(
                diff="--- a/app/orders/router.py\n+++ b/app/orders/router.py\n",
                changed_files=["app/orders/router.py"],
                log="stub harness applied idempotency scaffold",
                tokens=0,
                model_calls=0,
                usd=0.0,
            )
        return HarnessResult(
            diff="",
            changed_files=[],
            log="stub harness: no further changes",
            tokens=0,
            model_calls=0,
            usd=0.0,
        )
