from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.models.deal import Deal, DealFunnel


class DealRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self, funnel: DealFunnel | None = None) -> list[Deal]:
        query = select(Deal).order_by(Deal.created_at.desc())
        if funnel is not None:
            query = query.where(Deal.funnel == funnel)
        result = await self.session.execute(query)
        return list(result.scalars().all())
