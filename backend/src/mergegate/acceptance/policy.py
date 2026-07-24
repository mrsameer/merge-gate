from __future__ import annotations

import fnmatch
from pathlib import Path

from mergegate.models import Contract, CriterionType, Policy, PolicyViolation

DEFAULT_FORBIDDEN_PATTERNS = [
    "pytest.mark.skip",
    "@pytest.mark.skip",
    "pytest.skip(",
]


def default_policy() -> Policy:
    return Policy(
        protected_paths=["app/auth/**"],
        forbidden_diff_patterns=list(DEFAULT_FORBIDDEN_PATTERNS),
    )


def extract_policy(contract: Contract, *, run_policy: Policy | None = None) -> Policy:
    protected_paths = list(run_policy.protected_paths if run_policy else [])
    forbidden_patterns = list(
        run_policy.forbidden_diff_patterns
        if run_policy and run_policy.forbidden_diff_patterns
        else DEFAULT_FORBIDDEN_PATTERNS
    )
    for criterion in contract.criteria:
        if (
            criterion.type == CriterionType.GIT_POLICY
            or criterion.id == "protected-files"
        ):
            protected_paths.extend(criterion.params.get("paths", []))
    if not protected_paths:
        protected_paths = ["app/auth/**"]
    return Policy(
        protected_paths=sorted(set(protected_paths)),
        forbidden_diff_patterns=sorted(set(forbidden_patterns)),
    )


def _matches_protected_path(path: str, pattern: str) -> bool:
    normalized = path.replace("\\", "/").lstrip("./")
    return fnmatch.fnmatch(normalized, pattern)


def check_policy(
    *,
    policy: Policy,
    changed_files: list[str],
    diff: str,
    workspace: Path | None = None,
) -> PolicyViolation | None:
    for rel_path in changed_files:
        normalized = rel_path.replace("\\", "/")
        for pattern in policy.protected_paths:
            if _matches_protected_path(normalized, pattern):
                return PolicyViolation(
                    kind="protected_path",
                    offender=normalized,
                    message=(
                        f"Change touches protected path {normalized} "
                        f"(pattern {pattern})"
                    ),
                )

    searchable_chunks = [diff]
    if workspace is not None:
        for rel_path in changed_files:
            file_path = workspace / rel_path
            if file_path.is_file():
                searchable_chunks.append(file_path.read_text(encoding="utf-8"))

    combined = "\n".join(searchable_chunks)
    for pattern in policy.forbidden_diff_patterns:
        if pattern in combined:
            return PolicyViolation(
                kind="forbidden_pattern",
                offender=pattern,
                message=f"Diff contains forbidden pattern: {pattern}",
            )

    return None
