"""Unit tests for T024 — the deterministic acceptance command runner.

These prove the single primitive every acceptance check relies on captures
stdout, stderr, exit code, and duration correctly, and that the two failure
modes that must never crash a run — a missing executable and a timeout — are
turned into well-defined results (Principle IV, FR-007).

`sys.executable` is used as the command under test so the suite is
self-contained and cross-platform (no dependence on shell built-ins).
"""

from __future__ import annotations

import sys
import time

from mergegate.acceptance.commands import (
    COMMAND_NOT_FOUND_EXIT_CODE,
    TIMEOUT_EXIT_CODE,
    CommandResult,
    run_command,
)


def _py(code: str) -> list[str]:
    """Argv that runs a snippet of Python via the current interpreter."""
    return [sys.executable, "-c", code]


def test_captures_stdout_and_zero_exit_code() -> None:
    result = run_command(_py("print('hello world')"))

    assert isinstance(result, CommandResult)
    assert result.exit_code == 0
    assert result.timed_out is False
    assert result.succeeded is True
    assert "hello world" in result.stdout
    assert result.stderr == ""


def test_captures_stderr_separately_from_stdout() -> None:
    result = run_command(
        _py("import sys; sys.stdout.write('OUT'); sys.stderr.write('ERR')")
    )

    assert result.exit_code == 0
    assert "OUT" in result.stdout
    assert "ERR" in result.stderr
    assert "ERR" not in result.stdout


def test_captures_nonzero_exit_code_and_marks_failure() -> None:
    result = run_command(_py("import sys; sys.exit(3)"))

    assert result.exit_code == 3
    assert result.succeeded is False
    assert result.timed_out is False


def test_records_duration_in_milliseconds() -> None:
    result = run_command(_py("import time; time.sleep(0.05)"))

    assert result.exit_code == 0
    assert result.duration_ms >= 40  # allow scheduler slack below the 50ms sleep


def test_timeout_is_captured_not_raised() -> None:
    result = run_command(_py("import time; time.sleep(30)"), timeout_s=0.5)

    assert result.timed_out is True
    assert result.exit_code == TIMEOUT_EXIT_CODE
    assert result.succeeded is False
    # The command was bounded well under its 30s sleep.
    assert result.duration_ms < 5_000


def test_timeout_terminates_child_processes_holding_capture_pipes(tmp_path) -> None:
    marker = tmp_path / "orphan-survived"
    child = (
        "import pathlib,time; "
        "time.sleep(0.8); "
        f"pathlib.Path({str(marker)!r}).write_text('survived')"
    )
    parent = (
        "import subprocess,sys,time; "
        f"subprocess.Popen([sys.executable, '-c', {child!r}]); "
        "time.sleep(30)"
    )

    result = run_command(_py(parent), timeout_s=0.1)
    time.sleep(1)

    assert result.timed_out is True
    assert result.duration_ms < 1_000
    assert not marker.exists()


def test_missing_executable_returns_127_without_raising() -> None:
    result = run_command(["this-command-does-not-exist-mergegate"])

    assert result.exit_code == COMMAND_NOT_FOUND_EXIT_CODE
    assert result.succeeded is False
    assert result.stderr != ""


def test_respects_working_directory(tmp_path) -> None:
    result = run_command(
        _py("import os; print(os.path.realpath(os.getcwd()))"),
        cwd=tmp_path,
    )

    assert result.exit_code == 0
    import os

    assert os.path.realpath(str(tmp_path)) in result.stdout.strip()
    assert result.cwd == os.fspath(tmp_path)


def test_extra_env_is_passed_to_child() -> None:
    result = run_command(
        _py("import os; print(os.environ.get('MG_TEST_VAR', 'MISSING'))"),
        extra_env={"MG_TEST_VAR": "present-42"},
    )

    assert result.exit_code == 0
    assert "present-42" in result.stdout


def test_accepts_string_command_via_shlex() -> None:
    result = run_command(f'"{sys.executable}" -c "print(1 + 1)"')

    assert result.exit_code == 0
    assert "2" in result.stdout


def test_empty_command_raises_value_error() -> None:
    import pytest

    with pytest.raises(ValueError):
        run_command([])


def test_result_is_immutable() -> None:
    import dataclasses

    import pytest

    result = run_command(_py("print('x')"))
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.exit_code = 99  # type: ignore[misc]
