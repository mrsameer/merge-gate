from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mergegate.acceptance.baseline import run_baseline_checks
from mergegate.acceptance.engine import PolicyBlockedError, run_acceptance_engine
from mergegate.acceptance.evidence import build_red_green_evidence
from mergegate.acceptance.policy import extract_policy
from mergegate.criteria.generate import generate_hybrid_criteria
from mergegate.harness.base import HarnessAdapter, HarnessResult
from mergegate.models import (
    AgentRole,
    CheckResult,
    Contract,
    Node,
    PolicyViolation,
    RedGreenEvidence,
    Run,
    StructuredFeedback,
    Verdict,
)
from mergegate.orchestrator.graph import default_four_role_loop
from mergegate.workspace.worktree import capture_attempt_diff


@dataclass
class NodeResult:
    role: AgentRole
    node_id: str
    status: str
    output: dict[str, Any] = field(default_factory=dict)


@dataclass
class AttemptContext:
    run: Run
    worktree_path: Path
    attempt_id: str
    attempt_index: int
    feedback: StructuredFeedback | None = None
    plan: str = ""
    harness_log: str = ""
    changed_files: list[str] = field(default_factory=list)
    harness_result: HarnessResult | None = None
    baseline_checks: list[CheckResult] = field(default_factory=list)
    verdict: Verdict | None = None
    evidence: RedGreenEvidence | None = None
    policy_violation: PolicyViolation | None = None
    node_results: list[NodeResult] = field(default_factory=list)


class FourRoleNodeRunner:
    """Wires the four agent roles to their delegated backends."""

    def __init__(self, *, harness: HarnessAdapter, repo_path: Path) -> None:
        self.harness = harness
        self.repo_path = repo_path
        self._workflow = default_four_role_loop("runtime")

    def _node_for_role(self, role: AgentRole) -> Node:
        for node in self._workflow.nodes:
            if node.config.role == role:
                return node
        raise KeyError(f"no workflow node for role {role}")

    def run_success_criteria(self, run: Run) -> NodeResult:
        """Success Criteria role — hybrid contract from objective + repo map."""
        node = self._node_for_role(AgentRole.SUCCESS_CRITERIA)
        contract = generate_hybrid_criteria(
            run_id=run.id,
            objective=run.objective,
            repo_path=self.repo_path,
        )
        return NodeResult(
            role=AgentRole.SUCCESS_CRITERIA,
            node_id=node.id,
            status="passed",
            output={"contract": contract},
        )

    def run_planning(self, ctx: AttemptContext) -> AttemptContext:
        """Planning role — revise the implementation plan from feedback."""
        node = self._node_for_role(AgentRole.PLANNING)
        plan_lines = [f"Objective: {ctx.run.objective}"]
        if ctx.feedback is not None:
            plan_lines.extend(
                [
                    f"Retry attempt: {ctx.feedback.attempt}",
                    f"Failed criterion: {ctx.feedback.criterion}",
                    f"Command: {ctx.feedback.command}",
                    f"Exit code: {ctx.feedback.exit_code}",
                    f"Location: {ctx.feedback.first_failing_location}",
                ]
            )
        ctx.plan = "\n".join(plan_lines)
        ctx.node_results.append(
            NodeResult(
                role=AgentRole.PLANNING,
                node_id=node.id,
                status="passed",
                output={"plan": ctx.plan},
            )
        )
        return ctx

    def run_execution(self, ctx: AttemptContext) -> AttemptContext:
        """Execution role — propose code changes via the harness adapter only."""
        node = self._node_for_role(AgentRole.EXECUTION)
        feedback = ctx.feedback.model_dump(mode="json") if ctx.feedback else None
        harness_result = self.harness.propose_changes(
            objective=ctx.run.objective,
            feedback=feedback,
            workspace=str(ctx.worktree_path),
        )
        ctx.harness_result = harness_result
        ctx.harness_log = harness_result.log
        ctx.changed_files = list(
            dict.fromkeys([*ctx.changed_files, *harness_result.changed_files])
        )
        ctx.node_results.append(
            NodeResult(
                role=AgentRole.EXECUTION,
                node_id=node.id,
                status="passed",
                output={
                    "log": harness_result.log,
                    "changed_files": harness_result.changed_files,
                    "model_calls": harness_result.model_calls,
                },
            )
        )
        return ctx

    def run_validation(self, ctx: AttemptContext) -> AttemptContext:
        """Validation role — deterministic acceptance engine, never the harness."""
        node = self._node_for_role(AgentRole.VALIDATION)
        if ctx.run.contract is None:
            raise ValueError("contract required for validation")
        policy = extract_policy(ctx.run.contract, run_policy=ctx.run.policy)
        attempt_diff = capture_attempt_diff(ctx.worktree_path, ctx.changed_files)
        try:
            verdict = run_acceptance_engine(
                attempt_id=ctx.attempt_id,
                contract=ctx.run.contract,
                workspace=ctx.worktree_path,
                changed_files=ctx.changed_files,
                diff=attempt_diff,
                policy=policy,
            )
        except PolicyBlockedError as exc:
            ctx.policy_violation = exc.violation
            ctx.node_results.append(
                NodeResult(
                    role=AgentRole.VALIDATION,
                    node_id=node.id,
                    status="failed",
                    output={
                        "policy_blocked": True,
                        "kind": exc.violation.kind,
                        "offender": exc.violation.offender,
                    },
                )
            )
            return ctx
        ctx.verdict = verdict
        ctx.evidence = self._build_evidence(ctx, ctx.run.contract, verdict)
        ctx.node_results.append(
            NodeResult(
                role=AgentRole.VALIDATION,
                node_id=node.id,
                status="passed" if verdict.passed else "failed",
                output={
                    "passed": verdict.passed,
                    "acceptance_hash": verdict.acceptance_hash,
                    "evidence_verdict": ctx.evidence.verdict if ctx.evidence else None,
                },
            )
        )
        return ctx

    def _build_evidence(
        self,
        ctx: AttemptContext,
        contract: Contract,
        verdict: Verdict,
    ) -> RedGreenEvidence | None:
        for criterion in contract.criteria:
            if criterion.baseline_expected is None:
                continue
            baseline = next(
                (c for c in ctx.baseline_checks if c.criterion_id == criterion.id),
                None,
            )
            result = next(
                (c for c in verdict.checks if c.criterion_id == criterion.id),
                None,
            )
            if baseline is not None and result is not None:
                return build_red_green_evidence(
                    criterion=criterion,
                    baseline=baseline,
                    result=result,
                )
        return None

    def execute_attempt(
        self,
        *,
        run: Run,
        worktree_path: Path,
        attempt_id: str,
        attempt_index: int,
        feedback: StructuredFeedback | None = None,
    ) -> AttemptContext:
        ctx = AttemptContext(
            run=run,
            worktree_path=worktree_path,
            attempt_id=attempt_id,
            attempt_index=attempt_index,
            feedback=feedback,
        )
        ctx = self.run_planning(ctx)
        prep = self.harness.prepare_acceptance_tests(
            objective=run.objective,
            workspace=str(worktree_path),
        )
        ctx.changed_files.extend(prep.changed_files)
        if run.contract is not None:
            ctx.baseline_checks = run_baseline_checks(
                run.contract,
                workspace=worktree_path,
            )
        ctx = self.run_execution(ctx)
        ctx = self.run_validation(ctx)
        return ctx


def contract_from_success_criteria(result: NodeResult) -> Contract:
    contract = result.output.get("contract")
    if not isinstance(contract, Contract):
        raise TypeError("success criteria node did not produce a contract")
    return contract
