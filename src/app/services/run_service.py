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

    # Progress: Executing (30%)
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
        )

        # Progress: Processing results (70%)
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
        await _persist_tool_reports(session, run.id, runner_response.get("context_variables", {}))
        await _persist_diff_summary(session, run.id, workspace)

        # Progress: Pattern extraction (85%)
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

        if error_info:
            await run_events.publish(
                run.id,
                {
                    "type": "error",
                    "run_id": run.id,
                    "error": error_info.to_dict(),
                },
            )

        await _update_status(session, run.id, "failed")
        raise

    # Progress: Complete (100%)
    elapsed = time.time() - start_time
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
        content = msg.get("content", "")
        if isinstance(content, list):
            content = json.dumps(content)
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
