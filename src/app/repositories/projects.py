from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Project


async def list_projects(session: AsyncSession) -> list[Project]:
    result = await session.execute(select(Project).order_by(Project.created_at.desc()))
    return list(result.scalars().all())


async def get_project(session: AsyncSession, project_id: str) -> Project | None:
    result = await session.execute(select(Project).where(Project.id == project_id))
    return result.scalar_one_or_none()


async def upsert_project(session: AsyncSession, project: Project) -> Project:
    existing = await get_project(session, project.id)
    if existing:
        existing.name = project.name
        existing.task_type = project.task_type
        existing.domain_config = project.domain_config
        await session.flush()
        return existing
    session.add(project)
    await session.flush()
    return project
