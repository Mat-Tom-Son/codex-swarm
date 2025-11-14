from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import shutil
import subprocess
from urllib.parse import quote

from sqlalchemy.ext.asyncio import AsyncSession

from .. import repositories
from ..database import AsyncSessionLocal
from ..config import settings
from ..models import Artifact, Run, Step
from ..services import patterns as pattern_service
from ..services import runner_client
from ..services import diff as diff_service
from ..services import pattern_agent
from ..services import machine_summary as machine_summary_service
from ..utils import new_id
from ..events import run_events

logger = logging.getLogger(__name__)


@dataclass
class RunRequest:
    project_id: str
    name: str
    instructions: str
    reference_run_id: str | None = None
    from_run_id: str | None = None


@dataclass
class RunCreation:
    run: Run
    pattern_block: str


async def queue_run(session: AsyncSession, req: RunRequest) -> RunCreation:
    pattern_block = ""
    if req.reference_run_id:
        pattern = await fetch_pattern(session, req.reference_run_id)
        if pattern:
            pattern_block = pattern_service.render_pattern_block(pattern)

    system_instructions = _compose_system_instructions(pattern_block, req.instructions)

    run = Run(
        id=new_id("run"),
        project_id=req.project_id,
        name=req.name,
        status="queued",
        reference_run_id=req.reference_run_id,
        workspace_from_run_id=req.from_run_id,
        system_instructions=system_instructions,
    )
    await repositories.runs.create_run(session, run)
    await run_events.publish(
        run.id,
        {
            "type": "status",
            "status": run.status,
            "run_id": run.id,
            "project_id": run.project_id,
        },
    )
    return RunCreation(run=run, pattern_block=pattern_block)


async def fetch_pattern(session: AsyncSession, run_id: str) -> pattern_service.Pattern | None:
    return await pattern_agent.fetch_pattern(session, run_id)


def _compose_system_instructions(pattern_block: str, run_prompt: str) -> str:
    blocks = []
    if pattern_block:
        blocks.append(pattern_block.strip())
    blocks.append(settings.base_prompt.strip())
    blocks.append(run_prompt.strip())
    return "\n\n".join(blocks).strip()


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _safe_path_segment(raw: str, fallback: str) -> str:
    trimmed = raw.strip()
    if not trimmed:
        trimmed = fallback
    encoded = quote(trimmed, safe="")
    return encoded or fallback


def _workspace_path(project_id: str, run_id: str) -> Path:
    root = settings.workspace_root.resolve()
    project_segment = _safe_path_segment(project_id, "project")
    run_segment = _safe_path_segment(run_id, "run")
    candidate = (root / project_segment / run_segment).resolve()
    if not candidate.is_relative_to(root):
        raise ValueError("Workspace path escaped workspace root")
    return candidate


def _ensure_git_repo(workspace: Path) -> None:
    git_dir = workspace / ".git"
    if git_dir.exists():
        return
    try:
        subprocess.run(
            ["git", "init", "-q"],
            cwd=str(workspace),
            check=True,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Git not available; proceed without initialization (Codex will skip repo check)
        pass


def _clone_workspace_contents(source: Path, destination: Path) -> list[str]:
    copied: list[str] = []
    try:
        if source.resolve() == destination.resolve():
            return copied
    except FileNotFoundError:
        return copied
    for entry in source.iterdir():
        target = destination / entry.name
        if entry.is_symlink():
            if target.exists() or target.is_symlink():
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            target.symlink_to(entry.readlink())
            copied.append(entry.name)
            continue
        if entry.is_dir():
            shutil.copytree(entry, target, dirs_exist_ok=True)
            copied.append(f"{entry.name}/")
            continue
        if entry.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(entry, target, follow_symlinks=False)
            copied.append(entry.name)
    return copied


def _prepare_workspace(
    project_id: str,
    run_id: str,
    from_run_id: str | None,
) -> tuple[Path, list[str], bool]:
    workspace = _workspace_path(project_id, run_id)
    workspace.mkdir(parents=True, exist_ok=True)
    cloned_entries: list[str] = []
    source_found = False
    if from_run_id and from_run_id != run_id:
        source_workspace = _workspace_path(project_id, from_run_id)
        if source_workspace.exists():
            source_found = True
            cloned_entries = _clone_workspace_contents(source_workspace, workspace)
    _ensure_git_repo(workspace)
    return workspace, cloned_entries, source_found


def _collect_workspace_files(workspace: Path) -> list[dict[str, Any]]:
    """Collect a summary of files in the workspace."""
    files = []
    if not workspace.exists():
        return files

    for path in workspace.rglob("*"):
        if path.is_file():
            rel_path = path.relative_to(workspace)
            # Skip .git internals
            if str(rel_path).startswith(".git/"):
                continue

            files.append({
                "path": str(rel_path),
                "size": path.stat().st_size,
            })

    return sorted(files, key=lambda f: f["path"])


async def launch_run(
    session: AsyncSession,
    run: Run,
    user_prompt: str,
    pattern_block: str,
    from_run_id: str | None = None,
) -> dict[str, Any]:
    import time

    start_time = time.time()

    # Progress: Workspace preparation (0-20%)
    await _update_progress(session, run.id, 0)
    await run_events.publish(
        run.id,
        {
            "type": "progress",
            "stage": "workspace_prep",
            "message": "Preparing workspace...",
            "percent": 0,
        },
    )

    source_run_id = from_run_id or run.workspace_from_run_id
    workspace, cloned_entries, source_found = _prepare_workspace(
        run.project_id, run.id, source_run_id
    )

    if source_run_id:
        event: dict[str, Any] = {
            "type": "workspace",
            "run_id": run.id,
            "source_run_id": source_run_id,
        }
        if source_found:
            event["action"] = "cloned"
            event["entries"] = cloned_entries
            await _update_progress(session, run.id, 20)
            await run_events.publish(
                run.id,
                {
                    "type": "progress",
                    "stage": "workspace_cloned",
                    "message": f"Cloned {len(cloned_entries)} items from previous run",
                    "percent": 20,
                    "details": {"files": cloned_entries[:10]},
                },
            )
        else:
            event["action"] = "clone-missing"
        await run_events.publish(run.id, event)
    else:
        await _update_progress(session, run.id, 20)
        await run_events.publish(
            run.id,
            {
                "type": "progress",
                "stage": "workspace_ready",
                "message": "Workspace ready",
                "percent": 20,
            },
        )

    await _update_status(session, run.id, "running")

    # Get project to determine task_type
    project = await repositories.projects.get_project(session, run.project_id)
    task_type = project.task_type if project else "code"
    resume_thread_id: str | None = None
    if run.reference_run_id:
        reference_run = await repositories.runs.get_run(session, run.reference_run_id)
        if reference_run and getattr(reference_run, "codex_thread_id", None):
            resume_thread_id = reference_run.codex_thread_id

    # Progress: Executing (30%)
    await _update_progress(session, run.id, 30)
    await run_events.publish(
        run.id,
        {
            "type": "progress",
            "stage": "executing",
            "message": "Running Codex agent on your task...",
            "percent": 30,
        },
    )

    try:
        runner_response = await runner_client.invoke_run(
            run_id=run.id,
            project_id=run.project_id,
            user_prompt=user_prompt,
            pattern_block=pattern_block,
            workspace=workspace,
            task_type=task_type,
            resume_thread_id=resume_thread_id,
        )

        # Progress: Processing results (70%)
        await _update_progress(session, run.id, 70)
        await run_events.publish(
            run.id,
            {
                "type": "progress",
                "stage": "processing_results",
                "message": "Processing execution results...",
                "percent": 70,
            },
        )

        await _persist_messages(session, run.id, runner_response.get("messages", []))
        context_variables = runner_response.get("context_variables", {})
        await _persist_tool_reports(session, run.id, context_variables)
        new_thread_id = context_variables.get("codex_thread_id")
        if new_thread_id:
            run.codex_thread_id = new_thread_id
            await session.flush()
        await _persist_diff_summary(session, run.id, workspace)

        # Progress: Pattern extraction (85%)
        await _update_progress(session, run.id, 85)
        await run_events.publish(
            run.id,
            {
                "type": "progress",
                "stage": "extracting_patterns",
                "message": "Learning patterns from this run...",
                "percent": 85,
            },
        )

        try:
            await pattern_agent.fetch_pattern(session, run.id)
        except Exception:
            logger.exception("Pattern agent failed for run %s", run.id)
    except Exception as exc:
        # Publish error event with helpful message
        from ..errors import parse_error_notes

        error_info = None
        if hasattr(exc, "args") and exc.args:
            error_info = parse_error_notes(exc.args)

        # Track error in run
        error_record = {
            "step": "execution",
            "tool": "runner",
            "error_type": "runtime_error",
            "message": str(exc),
        }

        if error_info:
            error_record["error_type"] = getattr(error_info, "error_type", "runtime_error")
            error_record["message"] = getattr(error_info, "message", str(exc))
            await run_events.publish(
                run.id,
                {
                    "type": "error",
                    "run_id": run.id,
                    "error": error_info.to_dict(),
                },
            )

        await _record_error(session, run.id, error_record)
        await session.rollback()
        await _update_status(session, run.id, "failed")
        raise

    # Progress: Complete (100%)
    elapsed = time.time() - start_time

    # Collect workspace file summary
    workspace_files = _collect_workspace_files(workspace)

    await _update_progress(session, run.id, 100)
    await run_events.publish(
        run.id,
        {
            "type": "progress",
            "stage": "complete",
            "message": f"Run completed in {elapsed:.1f}s",
            "percent": 100,
            "elapsed": elapsed,
        },
    )

    # Publish workspace summary
    if workspace_files:
        await run_events.publish(
            run.id,
            {
                "type": "workspace_summary",
                "run_id": run.id,
                "files": workspace_files[:20],  # First 20 files
                "total_files": len(workspace_files),
            },
        )

    # Generate machine summary for DraftPunk
    await _generate_and_store_summary(session, run.id, workspace)

    await _update_status(session, run.id, "succeeded")
    return runner_response


async def _persist_messages(
    session: AsyncSession,
    run_id: str,
    messages: list[dict[str, Any]],
) -> None:
    for msg in messages:
        role = msg.get("role")
        if role not in {"user", "assistant"}:
            continue
        content = _serialize_message_content(msg)
        step = Step(
            id=new_id("step"),
            run_id=run_id,
            t=_now_iso(),
            role=role,
            content=content,
        )
        await repositories.steps.record_step(session, step)
        await run_events.publish(
            run_id,
            {
                "type": "step",
                "step_id": step.id,
                "role": role,
                "content": content,
                "t": step.t,
            },
        )


async def _persist_tool_reports(
    session: AsyncSession,
    run_id: str,
    context_variables: dict[str, Any],
) -> None:
    reports = context_variables.get("tool_reports") or []
    for report in reports:
        files = report.get("files", [])
        notes = report.get("notes", [])
        step = Step(
            id=new_id("step"),
            run_id=run_id,
            t=_now_iso(),
            role="tool",
            content=f"{report.get('tool','tool')} result",
            outcome_ok=report.get("ok"),
            files_json=json.dumps(files),
            outcome_notes_json=json.dumps(notes),
            tool_name=report.get("tool"),
            tool_args_json=json.dumps({"prompt": report.get("prompt")}),
        )
        await repositories.steps.record_step(session, step)
        await run_events.publish(
            run_id,
            {
                "type": "step",
                "step_id": step.id,
                "role": "tool",
                "content": step.content,
                "t": step.t,
                "files": files,
                "notes": notes,
                "ok": report.get("ok"),
            },
        )

        artifact_path = report.get("artifact_path")
        if artifact_path:
            byte_count = int(report.get("bytes") or 0)
            # Codex execution logs are always JSONL format
            # Future: could also register output files created during execution
            artifact = Artifact(
                id=new_id("artifact"),
                run_id=run_id,
                kind="codex-jsonl",  # Execution log from Codex CLI
                path=artifact_path,
                bytes=byte_count,
            )
            await repositories.artifacts.add_artifact(session, artifact)
            await run_events.publish(
                run_id,
                {
                    "type": "artifact",
                    "artifact_id": artifact.id,
                    "path": artifact.path,
                    "bytes": artifact.bytes,
                },
            )


async def _persist_diff_summary(session: AsyncSession, run_id: str, workspace: Path) -> None:
    diff_summary = diff_service.collect_git_diff_summary(workspace)
    if not diff_summary:
        return

    artifact_path = settings.artifacts_root / f"{run_id}-diff.json"
    diff_service.write_diff_artifact(artifact_path, diff_summary)

    artifact = Artifact(
        id=new_id("artifact"),
        run_id=run_id,
        kind="diff-summary",
        path=str(artifact_path),
        bytes=artifact_path.stat().st_size,
    )
    await repositories.artifacts.add_artifact(session, artifact)
    await run_events.publish(
        run_id,
        {
            "type": "diff",
            "run_id": run_id,
            "artifact_id": artifact.id,
            "diff": diff_summary,
        },
    )


async def _update_status(session: AsyncSession, run_id: str, status: str) -> None:
    await repositories.runs.update_run_status(session, run_id, status)
    await session.commit()
    await run_events.publish(
        run_id,
        {
            "type": "status",
            "status": status,
            "run_id": run_id,
        },
    )


async def _update_progress(session: AsyncSession, run_id: str, progress: int) -> None:
    """Update run progress percentage."""
    await repositories.runs.update_run_progress(session, run_id, progress)
    await session.flush()


async def _record_error(session: AsyncSession, run_id: str, error_record: dict[str, Any]) -> None:
    """Record a structured error for the run."""
    # Load existing errors
    run = await repositories.runs.get_run(session, run_id)
    if not run:
        return

    errors = []
    if run.errors_json:
        try:
            errors = json.loads(run.errors_json)
        except json.JSONDecodeError:
            pass

    # Append new error
    errors.append(error_record)

    # Update run
    await repositories.runs.update_run_errors(
        session,
        run_id,
        had_errors=True,
        errors_json=json.dumps(errors),
    )
    await session.flush()


async def _generate_and_store_summary(
    session: AsyncSession,
    run_id: str,
    workspace: Path,
) -> None:
    """Generate and store machine summary for a completed run."""
    # Fetch run with all data
    run = await repositories.runs.get_run(session, run_id)
    if not run:
        return

    # Fetch steps and artifacts
    from ..repositories import steps as steps_repo
    from ..repositories import artifacts as artifacts_repo

    run_steps = await steps_repo.list_steps(session, run_id)
    run_artifacts = await artifacts_repo.list_artifacts(session, run_id)

    # Generate summary
    summary = machine_summary_service.generate_machine_summary(
        run=run,
        steps=run_steps,
        artifacts=run_artifacts,
        workspace_path=workspace,
    )

    # Store as JSON
    summary_json = json.dumps(summary)
    await repositories.runs.update_run_summary(session, run_id, summary_json)
    await session.flush()


def _serialize_message_content(msg: dict[str, Any]) -> str:
    """
    Normalize assistant/user message content into a string so it always
    fits the NOT NULL constraint on Step.content. Some responses only
    contain tool/function calls, so we persist those as JSON.
    """
    content = msg.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, (list, dict)):
        return json.dumps(content)
    if content is not None:
        return str(content)

    for key in ("tool_calls", "function_call"):
        data = msg.get(key)
        if data:
            return json.dumps({key: data})
    return ""


async def launch_run_background(
    run_id: str,
    user_prompt: str,
    pattern_block: str,
    from_run_id: str | None = None,
) -> None:
    async with AsyncSessionLocal() as session:
        run = await repositories.runs.get_run(session, run_id)
        if not run:
            return
        try:
            await launch_run(
                session=session,
                run=run,
                user_prompt=user_prompt,
                pattern_block=pattern_block,
                from_run_id=from_run_id,
            )
        except Exception:
            # launch_run already emits failure status; nothing else to add here.
            return
