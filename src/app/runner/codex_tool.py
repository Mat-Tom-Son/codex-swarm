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
    """Ensure the Codex CLI is authenticated. Returns (ok, notes)."""
    notes: list[str] = []
    if env.get("CROSS_RUN_FAKE_CODEX") == "1":
        return True, notes

    try:
        status = subprocess.run(
            ["codex", "login", "status"],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        if status.returncode == 0:
            return True, notes
        key = env.get("OPENAI_API_KEY")
        if not key:
            notes.append("codex-login-missing-key")
            return False, notes
        login = subprocess.run(
            ["codex", "login", "--with-api-key"],
            input=f"{key}\n",
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        if login.returncode != 0:
            stderr = (login.stderr or "").strip()
            stdout = (login.stdout or "").strip()
            failure = stderr or stdout or "unknown failure"
            notes.append(f"codex-login-failed:{failure[:200]}")
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
    resume_thread_id = context_variables.get("codex_resume_thread_id")

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

    cmd: list[str] = [
        "codex",
        "exec",
        "--json",
        "--cd",
        workspace,
    ]
    if settings.codex_full_auto:
        cmd.append("--full-auto")
    if profile:
        notes.append(f"profile:{profile}")
    if skip_git_check:
        cmd.append("--skip-git-repo-check")
        notes.append("skip-git-repo-check")

    if resume_thread_id:
        cmd.extend(["resume", resume_thread_id])
        if prompt:
            cmd.append(prompt)
    else:
        cmd.append(prompt)

    thread_id: str | None = None
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
                        continue

                    evt_type = evt.get("type")
                    if evt_type == "thread.started":
                        thread_id = evt.get("thread_id") or thread_id
                    elif evt_type == "item.completed":
                        item = evt.get("item") or {}
                        if item.get("type") == "command_execution":
                            cmd_text = item.get("command") or ""
                            exit_code = item.get("exit_code")
                            notes.append(f"cmd:{cmd_text} exit:{exit_code}")
                    elif evt_type in {"run.failed", "error"}:
                        ok = False

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

    if thread_id:
        context_variables["codex_thread_id"] = thread_id

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
