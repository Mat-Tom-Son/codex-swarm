from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Run


async def list_runs(session: AsyncSession, project_id: str | None = None) -> list[Run]:
    stmt = select(Run).order_by(Run.created_at.desc())
    if project_id:
        stmt = stmt.where(Run.project_id == project_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_run(session: AsyncSession, run_id: str) -> Run | None:
    result = await session.execute(select(Run).where(Run.id == run_id))
    return result.scalar_one_or_none()


async def create_run(session: AsyncSession, run: Run) -> Run:
    session.add(run)
    await session.flush()
    return run


async def update_run_status(session: AsyncSession, run_id: str, status: str) -> None:
    await session.execute(update(Run).where(Run.id == run_id).values(status=status))


async def update_run_progress(session: AsyncSession, run_id: str, progress: int) -> None:
    """Update run progress (0-100)."""
    await session.execute(update(Run).where(Run.id == run_id).values(progress=progress))


async def update_run_errors(
    session: AsyncSession,
    run_id: str,
    had_errors: bool,
    errors_json: str | None,
) -> None:
    """Update run error tracking."""
    await session.execute(
        update(Run)
        .where(Run.id == run_id)
        .values(had_errors=had_errors, errors_json=errors_json)
    )


async def update_run_summary(session: AsyncSession, run_id: str, machine_summary_json: str) -> None:
    """Update run machine summary."""
    await session.execute(
        update(Run).where(Run.id == run_id).values(machine_summary_json=machine_summary_json)
    )
