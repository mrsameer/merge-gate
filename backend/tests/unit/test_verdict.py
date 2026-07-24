"""Unit tests for T026 — pure-function verdict computation.

Covers:
* ``passed`` is ``True`` only when there is at least one check and all pass;
  a failing check or an empty check list fails the verdict (Principle IV:
  absence of verification is not success);
* ``acceptance_hash`` is deterministic for identical inputs, changes when a
  decision-relevant field (``passed``/``exit_code``) changes, and is stable
  when only non-deterministic capture fields (``stdout``/``duration_ms``)
  change — proving those are excluded from the hash;
* ``replay_of`` is threaded through onto the returned ``Verdict``.
"""

from __future__ import annotations

from mergegate.acceptance.verdict import acceptance_hash, compute_verdict
from mergegate.models.enums import CheckStep, PassFail
from mergegate.models.verdict import CheckResult


def _check(
    *,
    criterion_id: str = "c1",
    step: CheckStep = CheckStep.BUILD,
    passed: bool = True,
    exit_code: int = 0,
    stdout: str = "ok",
    stderr: str = "",
    duration_ms: int = 10,
    baseline_result: PassFail | None = None,
) -> CheckResult:
    return CheckResult(
        criterion_id=criterion_id,
        step=step,
        passed=passed,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_ms=duration_ms,
        baseline_result=baseline_result,
    )


ACCEPTANCE_INPUT: dict = {"contract_hash": "abc123", "workspace": "wt-1"}


def test_all_checks_pass_is_true() -> None:
    checks = [
        _check(criterion_id="c1", step=CheckStep.BUILD),
        _check(criterion_id="c2", step=CheckStep.LINT),
    ]
    verdict = compute_verdict(
        attempt_id="a1", checks=checks, acceptance_input=ACCEPTANCE_INPUT
    )
    assert verdict.passed is True


def test_any_check_fails_is_false() -> None:
    checks = [
        _check(criterion_id="c1", passed=True),
        _check(criterion_id="c2", step=CheckStep.LINT, passed=False, exit_code=1),
    ]
    verdict = compute_verdict(
        attempt_id="a1", checks=checks, acceptance_input=ACCEPTANCE_INPUT
    )
    assert verdict.passed is False


def test_empty_checks_is_not_a_pass() -> None:
    verdict = compute_verdict(
        attempt_id="a1", checks=[], acceptance_input=ACCEPTANCE_INPUT
    )
    assert verdict.passed is False


def test_hash_is_deterministic_for_identical_inputs() -> None:
    checks = [_check(criterion_id="c1"), _check(criterion_id="c2")]
    first = acceptance_hash(checks, ACCEPTANCE_INPUT)
    second = acceptance_hash(
        [_check(criterion_id="c1"), _check(criterion_id="c2")],
        dict(ACCEPTANCE_INPUT),
    )
    assert first == second
    # And the verdict surfaces the same digest as the helper.
    verdict = compute_verdict(
        attempt_id="a1", checks=checks, acceptance_input=ACCEPTANCE_INPUT
    )
    assert verdict.acceptance_hash == first
    assert len(first) == 64


def test_hash_changes_when_passed_changes() -> None:
    base = [_check(criterion_id="c1", passed=True)]
    changed = [_check(criterion_id="c1", passed=False)]
    assert acceptance_hash(base, ACCEPTANCE_INPUT) != acceptance_hash(
        changed, ACCEPTANCE_INPUT
    )


def test_hash_changes_when_exit_code_changes() -> None:
    base = [_check(criterion_id="c1", exit_code=0)]
    changed = [_check(criterion_id="c1", exit_code=1)]
    assert acceptance_hash(base, ACCEPTANCE_INPUT) != acceptance_hash(
        changed, ACCEPTANCE_INPUT
    )


def test_hash_changes_when_acceptance_input_changes() -> None:
    checks = [_check(criterion_id="c1")]
    other_input = {"contract_hash": "different", "workspace": "wt-1"}
    assert acceptance_hash(checks, ACCEPTANCE_INPUT) != acceptance_hash(
        checks, other_input
    )


def test_hash_ignores_non_deterministic_capture_fields() -> None:
    base = [_check(criterion_id="c1", stdout="ok", stderr="", duration_ms=10)]
    noisy = [
        _check(
            criterion_id="c1",
            stdout="totally different output",
            stderr="warnings galore",
            duration_ms=99999,
        )
    ]
    assert acceptance_hash(base, ACCEPTANCE_INPUT) == acceptance_hash(
        noisy, ACCEPTANCE_INPUT
    )


def test_baseline_result_participates_in_hash() -> None:
    base = [_check(criterion_id="c1", baseline_result=None)]
    changed = [_check(criterion_id="c1", baseline_result=PassFail.FAIL)]
    assert acceptance_hash(base, ACCEPTANCE_INPUT) != acceptance_hash(
        changed, ACCEPTANCE_INPUT
    )


def test_replay_of_is_threaded_through() -> None:
    checks = [_check(criterion_id="c1")]
    verdict = compute_verdict(
        attempt_id="a2",
        checks=checks,
        acceptance_input=ACCEPTANCE_INPUT,
        replay_of="a1",
    )
    assert verdict.replay_of == "a1"
    assert verdict.attempt_id == "a2"

    default_verdict = compute_verdict(
        attempt_id="a1", checks=checks, acceptance_input=ACCEPTANCE_INPUT
    )
    assert default_verdict.replay_of is None
