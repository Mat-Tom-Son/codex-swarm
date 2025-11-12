from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Iterable


def _run_git_command(workspace: Path, args: Iterable[str]) -> subprocess.CompletedProcess[str] | None:
    cmd = ["git", "-C", str(workspace), *args]
    try:
        return subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None


def collect_git_diff_summary(workspace: Path) -> dict | None:
    """Return a lightweight summary of git changes for the workspace, if any."""

    workspace = Path(workspace)
    probe = _run_git_command(workspace, ["rev-parse", "--is-inside-work-tree"])
    if not probe or probe.returncode != 0:
        return None

    status_proc = _run_git_command(workspace, ["status", "-sb"])
    if not status_proc or status_proc.returncode != 0:
        return None

    lines = status_proc.stdout.strip().splitlines()
    if not lines:
        return None

    branch_line = ""
    files: list[dict[str, str]] = []

    for line in lines:
        if line.startswith("##"):
            branch_line = line[2:].strip()
            continue
        if not line.strip():
            continue
        status = line[:2].strip()
        path = line[3:].strip()
        files.append({"path": path, "status": status})

    if not files:
        return None

    shortstat_proc = _run_git_command(workspace, ["diff", "--shortstat"])
    shortstat = shortstat_proc.stdout.strip() if shortstat_proc and shortstat_proc.stdout else ""

    stat_proc = _run_git_command(workspace, ["diff", "--stat", "--", "."])
    stat_text = stat_proc.stdout.strip() if stat_proc and stat_proc.stdout else ""

    return {
        "branch": branch_line,
        "files": files,
        "shortstat": shortstat,
        "stat": stat_text,
    }


def write_diff_artifact(path: Path, diff_summary: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(diff_summary, indent=2), encoding="utf-8")
