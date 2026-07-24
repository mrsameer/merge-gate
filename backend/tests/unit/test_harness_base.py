"""Unit tests for T015 — the `HarnessAdapter` provider interface (FR-034,
FR-035, research.md R5).

The whole point of this interface is that the orchestrator can drive any
coding harness through one method and one result shape, so a provider can be
swapped via configuration without touching the workflow definition. These
tests exercise that contract directly: the interface can't be instantiated on
its own, a concrete adapter that implements it works through the base type,
and the result/error types carry the shape data-model.md's `ProviderAdapter`
describes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mergegate.harness.base import HarnessAdapter, HarnessError, HarnessResult
from mergegate.models.attempt import StructuredFeedback
from mergegate.workspace.worktree import Worktree


def _workspace(tmp_path: Path) -> Worktree:
    """A `Worktree` value good enough to pass through an adapter call — the
    interface only needs to hand it to a provider, never inspect it.
    """
    return Worktree(
        path=tmp_path / "attempt-1",
        branch="mergegate/attempt-1",
        base_repo=tmp_path / "base-repo",
        base_commit="deadbeef",
    )


class _EchoAdapter(HarnessAdapter):
    """Minimal concrete adapter used to prove the interface is usable."""

    def propose_changes(
        self,
        objective: str,
        feedback: StructuredFeedback | None,
        workspace: Worktree,
    ) -> HarnessResult:
        return HarnessResult(
            diff=f"# {objective}",
            changed_files=["app.py"],
            log="ok",
            tokens=42,
            model_calls=1,
            usd=0.01,
        )


class _ExplodingAdapter(HarnessAdapter):
    """Adapter that fails to invoke the harness at all."""

    def propose_changes(
        self,
        objective: str,
        feedback: StructuredFeedback | None,
        workspace: Worktree,
    ) -> HarnessResult:
        raise HarnessError("cursor-agent executable not found")


def test_harness_adapter_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        HarnessAdapter()  # type: ignore[abstract]


def test_harness_adapter_subclass_missing_propose_changes_is_still_abstract() -> None:
    class _Incomplete(HarnessAdapter):
        pass

    with pytest.raises(TypeError):
        _Incomplete()  # type: ignore[abstract]


def test_concrete_adapter_returns_harness_result(tmp_path: Path) -> None:
    adapter: HarnessAdapter = _EchoAdapter()

    result = adapter.propose_changes(
        "make POST /orders idempotent", None, _workspace(tmp_path)
    )

    assert isinstance(result, HarnessResult)
    assert result.diff == "# make POST /orders idempotent"
    assert result.changed_files == ["app.py"]
    assert result.tokens == 42
    assert result.model_calls == 1
    assert result.usd == 0.01


def test_concrete_adapter_receives_prior_feedback(tmp_path: Path) -> None:
    seen: list[StructuredFeedback | None] = []

    class _RecordingAdapter(HarnessAdapter):
        def propose_changes(
            self,
            objective: str,
            feedback: StructuredFeedback | None,
            workspace: Worktree,
        ) -> HarnessResult:
            seen.append(feedback)
            return HarnessResult(diff="")

    feedback = StructuredFeedback(
        criterion="existing_tests",
        command="pytest",
        exit_code=1,
        failure_signature="AssertionError: idempotency key missing",
        attempt=1,
    )

    _RecordingAdapter().propose_changes("objective", feedback, _workspace(tmp_path))

    assert seen == [feedback]


def test_harness_result_defaults_to_empty_change_set() -> None:
    result = HarnessResult(diff="")

    assert result.changed_files == []
    assert result.log == ""
    assert result.tokens == 0
    assert result.model_calls == 0
    assert result.usd == 0.0


def test_harness_error_propagates_from_propose_changes(tmp_path: Path) -> None:
    adapter: HarnessAdapter = _ExplodingAdapter()

    with pytest.raises(HarnessError):
        adapter.propose_changes("objective", None, _workspace(tmp_path))


def test_harness_error_is_a_runtime_error() -> None:
    assert issubclass(HarnessError, RuntimeError)
