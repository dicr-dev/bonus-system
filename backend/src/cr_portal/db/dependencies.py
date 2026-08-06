from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.db.session import AsyncSessionLocal


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session