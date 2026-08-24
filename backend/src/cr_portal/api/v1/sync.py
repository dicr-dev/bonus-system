from fastapi import APIRouter,Depends
from sqlalchemy.ext.asyncio import AsyncSession
from cr_portal.api.deps import db_session,bitrix_client
from cr_portal.services.bitrix_sync import sync_users,sync_deals
router=APIRouter()
@router.post('/all')
async def all_sync(s:AsyncSession=Depends(db_session),c=Depends(bitrix_client)): return {'users':await sync_users(s,c),'deals':await sync_deals(s,c)}
