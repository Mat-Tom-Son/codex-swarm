from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ... import repositories
from ...models import Project
from ...schemas import ProjectCreate, ProjectRead, RunCreate, RunRead
from ...services import run_service
from ..deps import db_session

router = APIRouter()


def _project_to_read(project: Project) -> ProjectRead:
    return ProjectRead(
        id=project.id,
        name=project.name,
        task_type=project.task_type,
        domain_config=project.domain_config,
        created_at=project.created_at,
    )


@router.get("", response_model=list[ProjectRead])
async def list_projects(session: AsyncSession = Depends(db_session)) -> list[ProjectRead]:
    projects = await repositories.projects.list_projects(session)
    return [_project_to_read(p) for p in projects]


@router.put(
    "/{project_id}",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
)
async def upsert_project(
    project_id: str,
    payload: ProjectCreate,
    session: AsyncSession = Depends(db_session),
) -> ProjectRead:
    if project_id != payload.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project ID mismatch between path and payload.",
    )
    project = Project(
        id=payload.id,
        name=payload.name,
        task_type=payload.task_type,
        domain_config=payload.domain_config,
    )
    saved = await repositories.projects.upsert_project(session, project)
    await session.commit()
    return _project_to_read(saved)


@router.post(
    "/{project_id}/runs",
    response_model=RunRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_run_for_project(
    project_id: str,
    payload: RunCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(db_session),
) -> RunRead:
    if payload.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project ID mismatch between path and payload.",
        )
    project = await repositories.projects.get_project(session, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    if payload.from_run_id:
        source_run = await repositories.runs.get_run(session, payload.from_run_id)
        if not source_run:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source run not found.")
        if source_run.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Source run belongs to a different project.",
            )

    creation = await run_service.queue_run(
        session,
        run_service.RunRequest(
            project_id=project_id,
            name=payload.name,
            instructions=payload.instructions,
            reference_run_id=payload.reference_run_id,
            from_run_id=payload.from_run_id,
        ),
    )
    await session.commit()
    background_tasks.add_task(
        run_service.launch_run_background,
        creation.run.id,
        payload.instructions,
        creation.pattern_block,
        payload.from_run_id,
    )
    run = creation.run
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
