from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4


@dataclass
class Worktree:
    path: Path
    branch: str


def create_worktree(repo_path: Path, base_dir: Path | None = None) -> Worktree:
    base_dir = base_dir or Path(tempfile.mkdtemp(prefix="mergegate-wt-"))
    base_dir.mkdir(parents=True, exist_ok=True)
    branch = f"mergegate/attempt-{uuid4().hex[:8]}"
    worktree_path = base_dir / branch.replace("/", "-")
    repo_path = repo_path.resolve()
    if (repo_path / ".git").exists():
        subprocess.run(
            ["git", "worktree", "add", "-B", branch, str(worktree_path), "HEAD"],
            cwd=str(repo_path),
            check=True,
            capture_output=True,
            text=True,
        )
    else:
        shutil.copytree(repo_path, worktree_path, dirs_exist_ok=True)
    return Worktree(path=worktree_path, branch=branch)


def capture_diff(worktree_path: Path) -> str:
    if (worktree_path / ".git").exists():
        completed = subprocess.run(
            ["git", "diff"],
            cwd=str(worktree_path),
            capture_output=True,
            text=True,
            check=False,
        )
        return completed.stdout
    return ""


def discard_worktree(worktree_path: Path, repo_path: Path) -> None:
    if (repo_path / ".git").exists() and (worktree_path / ".git").exists():
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree_path)],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            check=False,
        )
    elif worktree_path.exists():
        shutil.rmtree(worktree_path, ignore_errors=True)
