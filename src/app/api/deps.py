from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session


async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_session():
        yield session
