from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Artifact


async def list_artifacts_for_run(session: AsyncSession, run_id: str) -> list[Artifact]:
    result = await session.execute(
        select(Artifact).where(Artifact.run_id == run_id).order_by(Artifact.created_at.desc())
    )
    return list(result.scalars().all())


async def add_artifact(session: AsyncSession, artifact: Artifact) -> Artifact:
    session.add(artifact)
    await session.flush()
    return artifact


async def get_artifact_by_kind(
    session: AsyncSession,
    run_id: str,
    kind: str,
) -> Artifact | None:
    result = await session.execute(
        select(Artifact)
        .where(Artifact.run_id == run_id, Artifact.kind == kind)
        .order_by(Artifact.created_at.desc())
    )
    return result.scalar_one_or_none()
