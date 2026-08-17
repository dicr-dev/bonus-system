from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self) -> list[User]:
        result = await self.session.execute(select(User).order_by(User.full_name))
        return list(result.scalars().all())

    async def get(self, user_id: UUID) -> User | None:
        return await self.session.get(User, user_id)
