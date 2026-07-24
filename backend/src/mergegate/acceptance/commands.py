from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass


@dataclass
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int


def run_command(
    command: str,
    *,
    cwd: str | None = None,
    timeout_s: int = 120,
) -> CommandResult:
    start = time.perf_counter()
    completed = subprocess.run(
        command,
        shell=True,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )
    duration_ms = int((time.perf_counter() - start) * 1000)
    return CommandResult(
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        duration_ms=duration_ms,
    )
