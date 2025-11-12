from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import PatternCache


async def get_cached_pattern(session: AsyncSession, run_id: str) -> PatternCache | None:
    result = await session.execute(select(PatternCache).where(PatternCache.source_run_id == run_id))
    return result.scalar_one_or_none()


async def save_pattern_cache(session: AsyncSession, cache: PatternCache) -> PatternCache:
    existing = await get_cached_pattern(session, cache.source_run_id)
    if existing:
        existing.summary = cache.summary
        existing.steps_json = cache.steps_json
        existing.variables_json = cache.variables_json
        await session.flush()
        return existing
    session.add(cache)
    await session.flush()
    return cache
