from __future__ import annotations

import json
import os
import subprocess
import threading
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

from ..config import settings

# Global registry of active processes for cancellation
_active_processes: dict[str, subprocess.Popen] = {}
_process_lock = threading.Lock()
_cancellation_flags: set[str] = set()
_cancellation_lock = threading.Lock()


def request_cancellation(run_id: str) -> bool:
    """Request cancellation of a running execution."""
    with _cancellation_lock:
        _cancellation_flags.add(run_id)

    # Try to terminate the process if it exists
    with _process_lock:
        proc = _active_processes.get(run_id)
        if proc and proc.poll() is None:  # Process is still running
            proc.terminate()
            return True
    return False


def _is_cancelled(run_id: str) -> bool:
    """Check if cancellation has been requested for this run."""
    with _cancellation_lock:
        return run_id in _cancellation_flags


def _clear_cancellation(run_id: str) -> None:
    """Clear cancellation flag after run completes."""
    with _cancellation_lock:
        _cancellation_flags.discard(run_id)


def _build_codex_env() -> dict[str, str]:
    env = os.environ.copy()
    key = settings.openai_api_key or env.get("OPENAI_API_KEY")
    if key:
        env["OPENAI_API_KEY"] = key
    return env


def _ensure_codex_login(env: dict[str, str]) -> tuple[bool, list[str]]:
    """Make sure codex CLI is authenticated. Returns (ok, notes)."""
    notes: list[str] = []
    if env.get("CROSS_RUN_FAKE_CODEX") == "1":
        return True, notes

    try:
        status = subprocess.run(
            ["codex", "login", "status"],
            capture_output=True,
            text=True,
            env=env,
        )
        if status.returncode == 0:
            return True, notes
        key = env.get("OPENAI_API_KEY")
        if not key:
            notes.append("codex-login-missing-key")
            return False, notes
        login = subprocess.run(
            ["codex", "login", "--with-api-key", key],
            capture_output=True,
            text=True,
            env=env,
        )
        if login.returncode != 0:
            stderr = (login.stderr or "").strip()[:200]
            notes.append(f"codex-login-failed:{stderr or login.stdout.strip()[:200]}")
            return False, notes
        return True, notes
    except FileNotFoundError:
        notes.append("codex-cli-not-found")
        return False, notes
    except Exception as exc:  # noqa: BLE001
        notes.append(f"codex-login-error:{exc}")
        return False, notes


def _write_fake_event(path: Path, prompt: str) -> Dict[str, Any]:
    payload = {"type": "run.end", "status": "succeeded", "prompt": prompt}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(payload) + "\n")
    return payload


def codex_exec(
    context_variables: Dict[str, Any],
    prompt: str,
    profile: Optional[str] = None,
) -> str:
    workspace = str(context_variables["workspace"])
    workspace_path = Path(workspace)
    has_git = (workspace_path / ".git").exists()
    skip_git_check = not settings.require_git_repo or not has_git
    run_id = context_variables.get("run_id", "run-unknown")
    profile = profile or context_variables.get("profile") or settings.codex_profile
    sandbox_flag = "--full-auto" if settings.codex_full_auto else ""

    artifact_dir = Path(settings.artifacts_root)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"{run_id}-codex-{uuid4().hex}.jsonl"

    files: set[str] = set()
    notes: list[str] = []
    ok = True

    fake = os.getenv("CROSS_RUN_FAKE_CODEX") == "1"
    if fake:
        _write_fake_event(artifact_path, prompt)
        report = {
            "tool": "codex_exec",
            "ok": True,
            "files": [],
            "notes": ["fake-codex-mode"],
            "artifact_path": str(artifact_path),
            "bytes": artifact_path.stat().st_size,
        }
        context_variables.setdefault("tool_reports", []).append(report)
        return "codex_exec(fake)"

    env = _build_codex_env()
    ready, login_notes = _ensure_codex_login(env)
    if not ready:
        notes.extend(login_notes or ["codex-login-required"])
        report = {
            "tool": "codex_exec",
            "ok": False,
            "files": [],
            "notes": notes,
            "artifact_path": str(artifact_path),
            "bytes": 0,
            "prompt": prompt,
        }
        context_variables.setdefault("tool_reports", []).append(report)
        return "codex_exec(login-needed)"
    notes.extend(login_notes)

    cmd = [
        "codex",
        "exec",
        "--json",
        "--profile",
        profile,
    ]
    if sandbox_flag:
        cmd.append(sandbox_flag)
    if skip_git_check:
        cmd.append("--skip-git-repo-check")
        notes.append("skip-git-repo-check")
    cmd.extend(["--cd", workspace, prompt])

    stderr_data = ""
    try:
        with artifact_path.open("w", encoding="utf-8") as artifact_file:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env=env,
            )
            assert proc.stdout is not None
            assert proc.stderr is not None

            # Register process for cancellation
            with _process_lock:
                _active_processes[run_id] = proc

            try:
                for line in proc.stdout:
                    # Check for cancellation
                    if _is_cancelled(run_id):
                        notes.append("cancelled-by-user")
                        proc.terminate()
                        try:
                            proc.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                        ok = False
                        break

                    artifact_file.write(line)
                    try:
                        evt = json.loads(line)
                    except json.JSONDecodeError:
                        notes.append("jsonl-parse-error")
                        continue
                    evt_type = evt.get("type") or evt.get("event")
                    if evt_type == "file.changed" and evt.get("path"):
                        files.add(evt["path"])
                    if evt_type in {"run.failed", "error"}:
                        ok = False
                    if evt_type == "command.result":
                        notes.append(f"cmd:{evt.get('cmd')} exit:{evt.get('exit_code')}")

                proc.stdout.close()
                stderr_data = proc.stderr.read()
                proc.wait()
            finally:
                # Unregister process
                with _process_lock:
                    _active_processes.pop(run_id, None)
                # Clear cancellation flag
                _clear_cancellation(run_id)

        if proc.returncode != 0:
            ok = False
            notes.append(f"codex-exit-{proc.returncode}")

        if stderr_data:
            notes.append(f"stderr:{stderr_data.strip()[:200]}")

    except FileNotFoundError:
        ok = False
        notes.append("codex-cli-not-found")
    except Exception as exc:  # noqa: BLE001
        ok = False
        notes.append(f"codex-error:{exc}")

    bytes_written = artifact_path.stat().st_size if artifact_path.exists() else 0

    report = {
        "tool": "codex_exec",
        "ok": ok,
        "files": sorted(files),
        "notes": notes,
        "artifact_path": str(artifact_path),
        "bytes": bytes_written,
        "prompt": prompt,
    }

    context_variables.setdefault("tool_reports", []).append(report)
    return f"codex_exec(ok={ok}, files={len(files)})"
