"""Deterministic anti-cheat policy evaluation (T049, FR-017, FR-018).

Policy evaluation consumes only the captured git diff and changed-file list.
It never invokes a model or executes repository code. Forbidden patterns are
checked only on added diff lines: deleting an existing skip marker must not be
misclassified as introducing one.
"""

from __future__ import annotations

from fnmatch import fnmatchcase

from mergegate.models import Policy, PolicyResult, PolicyViolation


def _normalize_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _matches_path(path: str, pattern: str) -> bool:
    normalized_path = _normalize_path(path)
    normalized_pattern = _normalize_path(pattern)
    return fnmatchcase(normalized_path, normalized_pattern)


def _added_lines(diff: str) -> list[tuple[str | None, str]]:
    """Return ``(target_path, text)`` pairs for additions in a unified diff."""
    current_path: str | None = None
    additions: list[tuple[str | None, str]] = []
    for line in diff.splitlines():
        if line.startswith("+++ "):
            raw_path = line[4:].split("\t", 1)[0]
            current_path = (
                _normalize_path(raw_path[2:])
                if raw_path.startswith("b/")
                else _normalize_path(raw_path)
            )
            continue
        if line.startswith("+") and not line.startswith("+++"):
            additions.append((current_path, line[1:]))
    return additions


def check_policy(
    policy: Policy,
    *,
    changed_files: list[str],
    diff: str,
) -> PolicyResult:
    """Evaluate protected paths and forbidden added-line patterns.

    Results preserve policy rule order and changed-file/diff order, making the
    first named offender stable for identical recorded input.
    """
    violations: list[PolicyViolation] = []
    normalized_files = [_normalize_path(path) for path in changed_files]

    for rule in policy.protected_paths:
        for path in normalized_files:
            if _matches_path(path, rule):
                violations.append(
                    PolicyViolation(
                        kind="protected_path",
                        offender=path,
                        rule=rule,
                        path=path,
                        message=(
                            f"protected path modified: {path} "
                            f"(matched policy rule {rule})"
                        ),
                    )
                )

    for rule in policy.forbidden_diff_patterns:
        seen_paths: set[str | None] = set()
        for path, line in _added_lines(diff):
            if rule not in line or path in seen_paths:
                continue
            seen_paths.add(path)
            location = f" in {path}" if path else ""
            violations.append(
                PolicyViolation(
                    kind="forbidden_pattern",
                    offender=rule,
                    rule=rule,
                    path=path,
                    message=f"forbidden diff pattern {rule!r} introduced{location}",
                )
            )

    return PolicyResult(passed=not violations, violations=violations)
