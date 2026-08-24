from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from cr_portal.models.deal import Deal
class DealRepository:
    def __init__(self,s:AsyncSession): self.s=s
    async def by_bitrix_id(self,i:int):
        r=await self.s.execute(select(Deal).where(Deal.bitrix_id==i)); return r.scalar_one_or_none()
    async def list(self,funnel:str|None=None,responsible_user_id:UUID|None=None,open_only:bool=False):
        q=select(Deal)
        if funnel: q=q.where(Deal.funnel==funnel)
        if responsible_user_id: q=q.where(Deal.responsible_user_id==responsible_user_id)
        if open_only: q=q.where(Deal.status=="in_progress")
        r=await self.s.execute(q.order_by(Deal.bitrix_id.desc())); return list(r.scalars().all())
