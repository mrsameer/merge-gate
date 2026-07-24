"""Unit tests for T025 — the LLM-free acceptance engine.

Covers:
* the pipeline runs criteria in `PIPELINE_ORDER`, ordered by priority within
  a step;
* `fail_fast` stops the pipeline at the first failed step (saving budget) and
  can be disabled to run everything;
* criteria without a recognized `step` are excluded, never crash the run;
* an end-to-end run against the real `demo-repo` fixture, proving the engine
  drives real files/commands/exit-codes rather than anything model-shaped
  (Constitution Principle I).
"""

from __future__ import annotations

import sys
from pathlib import Path

from mergegate.acceptance.engine import (
    PIPELINE_ORDER,
    AcceptanceEngine,
    run_acceptance_pipeline,
)
from mergegate.models.contract import Contract, Criterion
from mergegate.models.enums import CheckStep, ContractMode, CriterionType

REPO_ROOT = Path(__file__).resolve().parents[3]
DEMO_REPO = REPO_ROOT / "demo-repo"


def _py_command(code: str) -> str:
    return f'"{sys.executable}" -c "{code}"'


def _criterion(
    id_: str, step: CheckStep, *, priority: int = 1, exit_code: int = 0
) -> Criterion:
    return Criterion(
        id=id_,
        type=CriterionType.COMMAND,
        priority=priority,
        step=step,
        command=_py_command(f"import sys; sys.exit({exit_code})"),
    )


def test_pipeline_order_matches_research_md() -> None:
    assert PIPELINE_ORDER == (
        CheckStep.BUILD,
        CheckStep.LINT,
        CheckStep.EXISTING_TESTS,
        CheckStep.NEW_TESTS,
        CheckStep.MIGRATION,
        CheckStep.COVERAGE,
        CheckStep.API_CONTRACT,
    )


def test_engine_runs_steps_in_pipeline_order(tmp_path: Path) -> None:
    contract = Contract(
        id="c1",
        run_id="r1",
        mode=ContractMode.HYBRID,
        criteria=[
            _criterion("api", CheckStep.API_CONTRACT),
            _criterion("build", CheckStep.BUILD),
            _criterion("tests", CheckStep.EXISTING_TESTS),
        ],
    )
    engine = AcceptanceEngine(fail_fast=False)
    results = engine.run(contract, str(tmp_path))

    assert [r.criterion_id for r in results] == ["build", "tests", "api"]


def test_engine_orders_criteria_within_a_step_by_priority(tmp_path: Path) -> None:
    contract = Contract(
        id="c1",
        run_id="r1",
        criteria=[
            _criterion("second", CheckStep.BUILD, priority=2),
            _criterion("first", CheckStep.BUILD, priority=1),
        ],
    )
    engine = AcceptanceEngine(fail_fast=False)
    results = engine.run(contract, str(tmp_path))

    assert [r.criterion_id for r in results] == ["first", "second"]


def test_fail_fast_stops_at_first_failed_step(tmp_path: Path) -> None:
    contract = Contract(
        id="c1",
        run_id="r1",
        criteria=[
            _criterion("build", CheckStep.BUILD, exit_code=1),
            _criterion("tests", CheckStep.EXISTING_TESTS),
        ],
    )
    engine = AcceptanceEngine(fail_fast=True)
    results = engine.run(contract, str(tmp_path))

    assert [r.criterion_id for r in results] == ["build"]
    assert results[0].passed is False


def test_fail_fast_disabled_runs_every_step_regardless(tmp_path: Path) -> None:
    contract = Contract(
        id="c1",
        run_id="r1",
        criteria=[
            _criterion("build", CheckStep.BUILD, exit_code=1),
            _criterion("tests", CheckStep.EXISTING_TESTS),
        ],
    )
    engine = AcceptanceEngine(fail_fast=False)
    results = engine.run(contract, str(tmp_path))

    assert [r.criterion_id for r in results] == ["build", "tests"]
    assert results[0].passed is False
    assert results[1].passed is True


def test_all_steps_passing_returns_all_check_results_passed(tmp_path: Path) -> None:
    contract = Contract(
        id="c1",
        run_id="r1",
        criteria=[
            _criterion("build", CheckStep.BUILD),
            _criterion("lint", CheckStep.LINT),
            _criterion("tests", CheckStep.EXISTING_TESTS),
        ],
    )
    results = run_acceptance_pipeline(contract, str(tmp_path))

    assert len(results) == 3
    assert all(r.passed for r in results)


def test_criteria_without_a_pipeline_step_are_excluded(tmp_path: Path) -> None:
    """A criterion with `step=None` (e.g. a policy criterion) is not run here."""
    out_of_scope = Criterion(
        id="protected-files",
        type=CriterionType.GIT_POLICY,
        priority=1,
        step=None,
    )
    in_scope = _criterion("build", CheckStep.BUILD)
    contract = Contract(id="c1", run_id="r1", criteria=[out_of_scope, in_scope])

    results = run_acceptance_pipeline(contract, str(tmp_path))

    assert [r.criterion_id for r in results] == ["build"]


def test_empty_contract_produces_no_check_results(tmp_path: Path) -> None:
    contract = Contract(id="c1", run_id="r1", criteria=[])
    results = run_acceptance_pipeline(contract, str(tmp_path))
    assert results == []


def test_missing_evaluator_for_step_raises_configuration_error(tmp_path: Path) -> None:
    import pytest

    contract = Contract(
        id="c1",
        run_id="r1",
        criteria=[_criterion("build", CheckStep.BUILD)],
    )
    engine = AcceptanceEngine(evaluators={})
    with pytest.raises(ValueError, match="no evaluator registered"):
        engine.run(contract, str(tmp_path))


# ---------------------------------------------------------------------------
# End-to-end against the real demo-repo fixture — proves the engine drives
# genuine files/commands/exit codes, not a model response (Principle I).
# ---------------------------------------------------------------------------


def test_engine_runs_real_pytest_suite_against_demo_repo() -> None:
    contract = Contract(
        id="c1",
        run_id="r1",
        criteria=[
            Criterion(
                id="existing-tests",
                type=CriterionType.COMMAND,
                priority=1,
                step=CheckStep.EXISTING_TESTS,
                command="uv run pytest tests -q",
                expected_exit_code=0,
            ),
        ],
    )
    results = run_acceptance_pipeline(contract, str(DEMO_REPO))

    assert len(results) == 1
    check = results[0]
    assert check.step == CheckStep.EXISTING_TESTS
    assert check.exit_code == 0
    assert check.passed is True
    assert "passed" in check.stdout


def test_engine_detects_a_genuinely_failing_demo_repo_selector() -> None:
    """A pytest selector matching zero tests exits non-zero (pytest's own
    "no tests collected" behavior) — a real, recorded failure the engine
    reports honestly rather than treating as a vacuous pass (FR-009, R3).
    """
    contract = Contract(
        id="c1",
        run_id="r1",
        criteria=[
            Criterion(
                id="idempotency-not-implemented-yet",
                type=CriterionType.COMMAND,
                priority=1,
                step=CheckStep.NEW_TESTS,
                command="uv run pytest tests -q -k test_idempotency_key_reuses_order",
            ),
        ],
    )
    results = run_acceptance_pipeline(contract, str(DEMO_REPO))

    check = results[0]
    assert check.exit_code != 0
    assert check.passed is False
