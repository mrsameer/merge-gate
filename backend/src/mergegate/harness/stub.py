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


class AlwaysFailHarnessAdapter(StubHarnessAdapter):
    """Adds acceptance tests but never fixes implementation — forces retries."""

    def propose_changes(
        self,
        *,
        objective: str,
        feedback: dict[str, Any] | None,
        workspace: str,
    ) -> HarnessResult:
        self.prepare_acceptance_tests(objective=objective, workspace=workspace)
        router = Path(workspace) / "app" / "orders" / "router.py"
        content = router.read_text(encoding="utf-8")
        attempt_num = int((feedback or {}).get("attempt", 0)) + 1
        marker = f"# stub-fail-attempt-{attempt_num}"
        if marker not in content:
            router.write_text(content + f"\n{marker}\n", encoding="utf-8")
            return HarnessResult(
                diff=(
                    "--- a/app/orders/router.py\n"
                    f"+++ b/app/orders/router.py\n+{marker}\n"
                ),
                changed_files=["app/orders/router.py"],
                log=f"stub-fail: non-fixing change on attempt {attempt_num}",
                model_calls=0,
            )
        return HarnessResult(
            diff="",
            changed_files=[],
            log="stub-fail: deliberately not implementing fix",
            model_calls=0,
        )


class NoProgressHarnessAdapter(StubHarnessAdapter):
    """Repeats the same non-fixing change every attempt — triggers no-progress."""

    _MARKER = "# stub-no-progress-attempt"

    def propose_changes(
        self,
        *,
        objective: str,
        feedback: dict[str, Any] | None,
        workspace: str,
    ) -> HarnessResult:
        self.prepare_acceptance_tests(objective=objective, workspace=workspace)
        router = Path(workspace) / "app" / "orders" / "router.py"
        content = router.read_text(encoding="utf-8")
        if self._MARKER not in content:
            router.write_text(content + f"\n{self._MARKER}\n", encoding="utf-8")
        return HarnessResult(
            diff="--- a/app/orders/router.py\n+++ b/app/orders/router.py\n# same\n",
            changed_files=["app/orders/router.py"],
            log="stub-no-progress: same non-fix applied",
            model_calls=0,
        )


class ProtectedPathHarnessAdapter(StubHarnessAdapter):
    """Edits a protected auth path — triggers POLICY_BLOCKED."""

    def propose_changes(
        self,
        *,
        objective: str,
        feedback: dict[str, Any] | None,
        workspace: str,
    ) -> HarnessResult:
        self.prepare_acceptance_tests(objective=objective, workspace=workspace)
        guard = Path(workspace) / "app" / "auth" / "guard.py"
        guard.write_text(
            guard.read_text(encoding="utf-8") + "\n# stub-policy-auth-edit\n",
            encoding="utf-8",
        )
        return HarnessResult(
            diff="--- a/app/auth/guard.py\n+++ b/app/auth/guard.py\n",
            changed_files=["app/auth/guard.py"],
            log="stub-policy-auth: edited protected auth module",
            model_calls=0,
        )


class ForbiddenPatternHarnessAdapter(StubHarnessAdapter):
    """Inserts pytest.mark.skip — triggers forbidden diff pattern block."""

    def propose_changes(
        self,
        *,
        objective: str,
        feedback: dict[str, Any] | None,
        workspace: str,
    ) -> HarnessResult:
        self.prepare_acceptance_tests(objective=objective, workspace=workspace)
        test_file = Path(workspace) / "tests" / "test_idempotency.py"
        test_file.write_text(
            test_file.read_text(encoding="utf-8") + "\n@pytest.mark.skip\n",
            encoding="utf-8",
        )
        orders_router = Path(workspace) / "app" / "orders" / "router.py"
        content = orders_router.read_text(encoding="utf-8")
        if "Idempotency-Key" not in content:
            replacement = (
                '"""Idempotent order creation\n\n'
                "    Requires Idempotency-Key header.\n"
                '    """\n\n'
                "    # Baseline stub"
            )
            orders_router.write_text(
                content.replace('"""Baseline stub', replacement),
                encoding="utf-8",
            )
        return HarnessResult(
            diff=(
                "--- a/tests/test_idempotency.py\n"
                "+++ b/tests/test_idempotency.py\n+@pytest.mark.skip\n"
            ),
            changed_files=["tests/test_idempotency.py", "app/orders/router.py"],
            log="stub-policy-skip: inserted forbidden skip marker",
            model_calls=0,
        )
