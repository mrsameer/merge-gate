from __future__ import annotations

from pathlib import Path
from typing import Any

from mergegate.harness.base import HarnessAdapter, HarnessResult

TASK_TEST = '''"""Task acceptance tests for idempotent orders."""
from pathlib import Path


def test_idempotency_key_documented_in_router() -> None:
    text = Path("app/orders/router.py").read_text(encoding="utf-8")
    assert "Idempotency-Key" in text
'''


class StubHarnessAdapter(HarnessAdapter):
    """Deterministic harness for tests and local demo — no model calls."""

    def prepare_acceptance_tests(
        self,
        *,
        objective: str,
        workspace: str,
    ) -> HarnessResult:
        root = Path(workspace)
        test_file = root / "tests" / "test_idempotency.py"
        if test_file.exists():
            return HarnessResult(
                diff="",
                changed_files=[],
                log="acceptance tests already present",
                model_calls=0,
            )
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text(TASK_TEST, encoding="utf-8")
        return HarnessResult(
            diff="--- /dev/null\n+++ b/tests/test_idempotency.py\n",
            changed_files=["tests/test_idempotency.py"],
            log="stub harness added task acceptance tests",
            model_calls=0,
        )

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
                log="stub harness applied idempotency implementation",
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
