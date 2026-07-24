from __future__ import annotations

import platform
import subprocess
from pathlib import Path

from mergegate.acceptance.evaluators import get_evaluator
from mergegate.acceptance.verdict import compute_verdict
from mergegate.models import AcceptanceInput, CheckResult, Contract, Verdict


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
) -> Verdict:
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
