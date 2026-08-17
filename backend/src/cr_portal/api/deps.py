from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.db.session import get_db


async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db():
        yield session


DBSession = Depends(db_session)
