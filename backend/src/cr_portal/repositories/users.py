from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from cr_portal.models.user import User
class UserRepository:
    def __init__(self,s:AsyncSession): self.s=s
    async def list(self):
        r=await self.s.execute(select(User).order_by(User.full_name)); return list(r.scalars().all())
    async def by_bitrix_id(self,i:int):
        r=await self.s.execute(select(User).where(User.bitrix_id==i)); return r.scalar_one_or_none()
    async def upsert(self,bitrix_id:int,email:str|None,full_name:str,position:str|None=None):
        u=await self.by_bitrix_id(bitrix_id)
        if u is None: u=User(bitrix_id=bitrix_id,email=email,full_name=full_name,position=position); self.s.add(u)
        else: u.email=email; u.full_name=full_name; u.position=position; u.is_active=True
        return u
