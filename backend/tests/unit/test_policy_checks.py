"""Deterministic anti-cheat policy checks for T049 / FR-017 / FR-018."""

from mergegate.acceptance.policy import check_policy
from mergegate.models import Policy


def test_protected_path_violation_names_path_and_matching_rule() -> None:
    result = check_policy(
        Policy(protected_paths=["app/auth/**"]),
        changed_files=["app/orders/router.py", "app/auth/security.py"],
        diff="",
    )

    assert result.passed is False
    assert len(result.violations) == 1
    violation = result.violations[0]
    assert violation.kind == "protected_path"
    assert violation.offender == "app/auth/security.py"
    assert violation.rule == "app/auth/**"


def test_forbidden_pattern_only_checks_added_diff_lines() -> None:
    result = check_policy(
        Policy(forbidden_diff_patterns=["pytest.mark.skip"]),
        changed_files=["tests/test_orders.py"],
        diff=(
            "--- a/tests/test_orders.py\n"
            "+++ b/tests/test_orders.py\n"
            "@@ -1,2 +1,2 @@\n"
            "-@pytest.mark.skip(reason='old skip removed')\n"
            "+def test_order_creation():\n"
            "+    assert True\n"
        ),
    )

    assert result.passed is True


def test_forbidden_pattern_violation_names_pattern_and_source_path() -> None:
    result = check_policy(
        Policy(forbidden_diff_patterns=["pytest.mark.skip"]),
        changed_files=["tests/test_orders.py"],
        diff=(
            "diff --git a/tests/test_orders.py b/tests/test_orders.py\n"
            "+++ b/tests/test_orders.py\n"
            "@@ -1,0 +1,2 @@\n"
            "+@pytest.mark.skip(reason='avoid failure')\n"
            "+def test_order_creation(): ...\n"
        ),
    )

    assert result.passed is False
    assert result.violations[0].kind == "forbidden_pattern"
    assert result.violations[0].offender == "pytest.mark.skip"
    assert result.violations[0].path == "tests/test_orders.py"
