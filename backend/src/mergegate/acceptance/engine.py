"""T025 — LLM-free acceptance engine.

Runs a frozen `Contract`'s criteria through the ordered, deterministic
pipeline from research.md R2::

    build -> lint -> existing_tests -> new_tests -> migration -> coverage
    -> api_contract

(`policy` is the eighth `CheckStep` but is deliberately excluded from this
pipeline — anti-cheat protected-path/forbidden-diff enforcement is a separate
module, `acceptance/policy.py` (US5), run by the orchestrator before the
verdict is finalized, not a criterion evaluator.)

This module never imports anything model-related (no LLM client, no prompt
building) — it only ever calls the pluggable `criterion-evaluator registry`
from `evaluators.py`, which in turn only ever calls the deterministic
`run_command` primitive from `commands.py` (T024). That chain is the physical
enforcement of Constitution Principle I: generation and acceptance are
different code, in different modules, and the engine has no path back to the
coding agent.

The engine produces an ordered `list[CheckResult]`; T026 (verdict.py) turns
that list into a `Verdict` (pass/fail + `acceptance_hash`) as a pure function.
This module intentionally does not compute a verdict itself, to keep "what ran"
(engine) and "what it means" (verdict) separately reviewable.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from mergegate.acceptance.evaluators import EVALUATOR_REGISTRY, Evaluator
from mergegate.models.contract import Contract, Criterion
from mergegate.models.enums import CheckStep
from mergegate.models.verdict import CheckResult

# The pipeline order the engine walks. `POLICY` is excluded on purpose — see
# module docstring; a criterion typed for a step outside this tuple (or with
# `step=None`) is simply not part of this engine's run.
PIPELINE_ORDER: tuple[CheckStep, ...] = (
    CheckStep.BUILD,
    CheckStep.LINT,
    CheckStep.EXISTING_TESTS,
    CheckStep.NEW_TESTS,
    CheckStep.MIGRATION,
    CheckStep.COVERAGE,
    CheckStep.API_CONTRACT,
)


def _criteria_by_step(criteria: list[Criterion]) -> dict[CheckStep, list[Criterion]]:
    """Group criteria by pipeline step, ordered within each step by priority.

    Criteria with `step=None` (or a step outside `PIPELINE_ORDER`, e.g.
    `POLICY`) are excluded — they are out of scope for this engine.
    """
    grouped: dict[CheckStep, list[Criterion]] = {step: [] for step in PIPELINE_ORDER}
    for criterion in criteria:
        step = criterion.step
        if step is not None and step in grouped:
            grouped[step].append(criterion)
    for step_criteria in grouped.values():
        step_criteria.sort(key=lambda c: c.priority)
    return grouped


@dataclass(frozen=True)
class AcceptanceEngine:
    """Runs a contract's criteria through the ordered, LLM-free pipeline.

    Attributes:
        evaluators: Step -> evaluator mapping. Defaults to the shared
            `EVALUATOR_REGISTRY`; tests and `T073` extensions can inject an
            override without touching this class.
        fail_fast: When `True` (the default), the pipeline stops at the first
            step containing a failed criterion — running lint after a failed
            build, or tests after a failed lint, produces no useful signal
            and wastes the attempt's time/wall-clock budget (FR-013). Set to
            `False` to run every step regardless, e.g. for a full evidence
            report.
    """

    evaluators: Mapping[CheckStep, Evaluator] = field(
        default_factory=lambda: dict(EVALUATOR_REGISTRY)
    )
    fail_fast: bool = True

    def run(self, contract: Contract, workspace: str) -> list[CheckResult]:
        """Run `contract.criteria` through the ordered pipeline at `workspace`.

        Args:
            contract: The frozen, approved contract (FR-002/FR-003). Only
                criteria whose `step` falls in `PIPELINE_ORDER` participate.
            workspace: Filesystem path each command runs in — the attempt's
                isolated git worktree (FR-011), or the baseline worktree for
                red-before checks (FR-009).

        Returns:
            An ordered list of `CheckResult`, one per evaluated criterion, in
            pipeline order and priority order within each step. Never raises
            for a failing or missing command — those are captured as failed
            `CheckResult`s by the evaluators/`run_command` (Principle IV).

        Raises:
            ValueError: If a criterion targets a pipeline step for which no
                evaluator is registered (a configuration error, not a runtime
                acceptance failure).
        """
        grouped = _criteria_by_step(contract.criteria)
        results: list[CheckResult] = []

        for step in PIPELINE_ORDER:
            step_criteria = grouped[step]
            if not step_criteria:
                continue

            evaluator = self.evaluators.get(step)
            if evaluator is None:
                raise ValueError(f"no evaluator registered for step {step!r}")

            step_failed = False
            for criterion in step_criteria:
                check = evaluator(criterion, workspace)
                results.append(check)
                if not check.passed:
                    step_failed = True

            if step_failed and self.fail_fast:
                break

        return results


# A ready-to-use engine with the default registry and fail-fast enabled,
# for callers (the orchestrator's validation node, T027) that don't need a
# custom registry or run-everything mode.
default_engine = AcceptanceEngine()


def run_acceptance_pipeline(
    contract: Contract,
    workspace: str,
    *,
    evaluators: Mapping[CheckStep, Evaluator] | None = None,
    fail_fast: bool = True,
) -> list[CheckResult]:
    """Convenience wrapper: run a contract through the pipeline in one call.

    Equivalent to ``AcceptanceEngine(evaluators=..., fail_fast=...).run(...)``.
    """
    if evaluators is None and fail_fast:
        return default_engine.run(contract, workspace)

    resolved = dict(evaluators) if evaluators is not None else EVALUATOR_REGISTRY
    engine = AcceptanceEngine(evaluators=resolved, fail_fast=fail_fast)
    return engine.run(contract, workspace)
