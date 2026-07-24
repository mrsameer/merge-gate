from __future__ import annotations

import platform
import subprocess
from pathlib import Path

from mergegate.acceptance.evaluators import get_evaluator
from mergegate.acceptance.policy import check_policy
from mergegate.acceptance.verdict import compute_verdict
from mergegate.models import (
    AcceptanceInput,
    CheckResult,
    Contract,
    Policy,
    PolicyViolation,
    Verdict,
)


class PolicyBlockedError(Exception):
    def __init__(self, violation: PolicyViolation) -> None:
        self.violation = violation
        super().__init__(violation.message)


def _tool_versions() -> dict[str, str]:
    versions: dict[str, str] = {"python": platform.python_version()}
    for tool in ("git", "uv"):
        try:
            completed = subprocess.run(
                [tool, "--version"],
                capture_output=True,
                text=True,
                check=False,
            )
            versions[tool] = completed.stdout.strip() or completed.stderr.strip()
        except OSError:
            versions[tool] = "unknown"
    return versions


def run_acceptance_engine(
    *,
    attempt_id: str,
    contract: Contract,
    workspace: Path,
    commit_sha: str = "HEAD",
    changed_files: list[str] | None = None,
    diff: str = "",
    policy: Policy | None = None,
) -> Verdict:
    if policy is not None and changed_files is not None:
        violation = check_policy(
            policy=policy,
            changed_files=changed_files,
            diff=diff,
            workspace=workspace,
        )
        if violation is not None:
            raise PolicyBlockedError(violation)

    checks: list[CheckResult] = []
    ordered = sorted(contract.criteria, key=lambda c: c.priority)
    for criterion in ordered:
        evaluator = get_evaluator(criterion)
        checks.append(evaluator.evaluate(criterion, workspace=workspace))

    acceptance_input = AcceptanceInput(
        commit_sha=commit_sha,
        validation_config={"criteria_ids": [c.id for c in ordered]},
        tool_versions=_tool_versions(),
        env_fingerprint=platform.platform(),
    )
    return compute_verdict(
        attempt_id=attempt_id,
        checks=checks,
        acceptance_input=acceptance_input,
    )
