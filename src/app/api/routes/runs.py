import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ... import repositories
from ...models import Artifact, Run, Step
from ...schemas import ArtifactRead, RunRead, StepRead
from ..deps import db_session
from ...events import run_events

router = APIRouter()


def _run_to_read(run: Run) -> RunRead:
    return RunRead(
        id=run.id,
        project_id=run.project_id,
        name=run.name,
        created_at=run.created_at,
        status=run.status,
        reference_run_id=run.reference_run_id,
        workspace_from_run_id=run.workspace_from_run_id,
        system_instructions=run.system_instructions,
    )


def _step_to_read(step: Step) -> StepRead:
    return StepRead(
        id=step.id,
        run_id=step.run_id,
        t=step.t,
        role=step.role,
        content=step.content,
        intent_kind=step.intent_kind,
        intent_target=step.intent_target,
        outcome_ok=step.outcome_ok,
        files_json=step.files_json,
        tool_name=step.tool_name,
        tool_args_json=step.tool_args_json,
        outcome_notes_json=step.outcome_notes_json,
    )


def _artifact_to_read(artifact: Artifact) -> ArtifactRead:
    return ArtifactRead(
        id=artifact.id,
        run_id=artifact.run_id,
        kind=artifact.kind,
        path=artifact.path,
        bytes=artifact.bytes,
        created_at=artifact.created_at,
    )


@router.get("", response_model=list[RunRead])
async def list_runs(
    project_id: str | None = None,
    session: AsyncSession = Depends(db_session),
) -> list[RunRead]:
    runs = await repositories.runs.list_runs(session, project_id=project_id)
    return [_run_to_read(run) for run in runs]


@router.get("/{run_id}", response_model=RunRead)
async def get_run(run_id: str, session: AsyncSession = Depends(db_session)) -> RunRead:
    run = await repositories.runs.get_run(session, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
    return _run_to_read(run)


@router.get("/{run_id}/steps", response_model=list[StepRead])
async def get_run_steps(run_id: str, session: AsyncSession = Depends(db_session)) -> list[StepRead]:
    run = await repositories.runs.get_run(session, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
    steps = await repositories.steps.list_steps_for_run(session, run_id)
    return [_step_to_read(step) for step in steps]


@router.get("/{run_id}/artifacts", response_model=list[ArtifactRead])
async def get_run_artifacts(
    run_id: str,
    session: AsyncSession = Depends(db_session),
) -> list[ArtifactRead]:
    run = await repositories.runs.get_run(session, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
    artifacts = await repositories.artifacts.list_artifacts_for_run(session, run_id)
    return [_artifact_to_read(artifact) for artifact in artifacts]


@router.get("/{run_id}/diff")
async def get_run_diff(
    run_id: str,
    session: AsyncSession = Depends(db_session),
):
    run = await repositories.runs.get_run(session, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
    artifact = await repositories.artifacts.get_artifact_by_kind(session, run_id, "diff-summary")
    if not artifact:
        raise HTTPException(status_code=404, detail="Diff summary not available.")
    path = Path(artifact.path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Diff artifact missing.") from None
    return {"artifact_id": artifact.id, "summary": data}


@router.get("/{run_id}/artifacts/{artifact_id}/download")
async def download_artifact(
    run_id: str,
    artifact_id: str,
    session: AsyncSession = Depends(db_session),
):
    """Download an artifact file."""
    run = await repositories.runs.get_run(session, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")

    # Get the specific artifact
    artifacts = await repositories.artifacts.list_artifacts_for_run(session, run_id)
    artifact = next((a for a in artifacts if a.id == artifact_id), None)

    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found.")

    artifact_path = Path(artifact.path)
    if not artifact_path.exists():
        raise HTTPException(status_code=404, detail="Artifact file not found on disk.")

    # Determine media type based on artifact kind
    media_type_map = {
        "codex-jsonl": "application/x-ndjson",
        "diff-summary": "application/json",
        "markdown": "text/markdown",
        "json": "application/json",
        "csv": "text/csv",
        "txt": "text/plain",
    }
    media_type = media_type_map.get(artifact.kind, "application/octet-stream")

    return FileResponse(
        path=artifact_path,
        media_type=media_type,
        filename=artifact_path.name,
    )


@router.get("/{run_id}/stream")
async def stream_run_events(
    run_id: str,
    request: Request,
    session: AsyncSession = Depends(db_session),
):
    run = await repositories.runs.get_run(session, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")

    queue = await run_events.subscribe(run_id)
    await queue.put({"type": "status", "status": run.status, "run_id": run_id})

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                event = await queue.get()
                payload = json.dumps(event, default=str)
                yield f"data: {payload}\n\n"
        finally:
            await run_events.unsubscribe(run_id, queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/{run_id}/cancel")
async def cancel_run(
    run_id: str,
    session: AsyncSession = Depends(db_session),
):
    """Cancel a running execution."""
    run = await repositories.runs.get_run(session, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.status not in ["queued", "running"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel run with status: {run.status}",
        )

    # Request cancellation from the codex tool
    from ...runner.codex_tool import request_cancellation

    killed = request_cancellation(run_id)

    # Update status to cancelled
    await repositories.runs.update_run_status(session, run_id, "cancelled")
    await session.commit()

    # Publish cancellation event
    await run_events.publish(
        run_id,
        {
            "type": "cancelled",
            "run_id": run_id,
            "process_killed": killed,
        },
    )

    return {"status": "cancelled", "process_killed": killed}


@router.get("/{run_id}/workspace/files")
async def list_workspace_files(
    run_id: str,
    session: AsyncSession = Depends(db_session),
):
    """List files in run workspace."""
    from ...services import run_service

    run = await repositories.runs.get_run(session, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    workspace = run_service._workspace_path(run.project_id, run.id)

    if not workspace.exists():
        return {"files": [], "workspace": str(workspace)}

    files = []
    for path in workspace.rglob("*"):
        if path.is_file():
            rel_path = path.relative_to(workspace)
            # Skip .git internals
            if str(rel_path).startswith(".git/"):
                continue

            files.append({
                "path": str(rel_path),
                "size": path.stat().st_size,
                "modified": path.stat().st_mtime,
            })

    return {
        "files": sorted(files, key=lambda f: f["path"]),
        "workspace": str(workspace),
        "total_files": len(files),
    }


@router.get("/{run_id}/workspace/files/{file_path:path}")
async def download_workspace_file(
    run_id: str,
    file_path: str,
    session: AsyncSession = Depends(db_session),
):
    """Download a specific file from workspace."""
    from ...services import run_service

    run = await repositories.runs.get_run(session, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    workspace = run_service._workspace_path(run.project_id, run.id)
    full_path = (workspace / file_path).resolve()

    # Security check: ensure path is within workspace
    if not full_path.is_relative_to(workspace):
        raise HTTPException(status_code=403, detail="Path traversal detected")

    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(full_path)
