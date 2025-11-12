from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Step


async def list_steps_for_run(session: AsyncSession, run_id: str) -> list[Step]:
    result = await session.execute(select(Step).where(Step.run_id == run_id).order_by(Step.t))
    return list(result.scalars().all())


async def record_step(session: AsyncSession, step: Step) -> Step:
    session.add(step)
    await session.flush()
    return step
