from collections.abc import AsyncGenerator
from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from cr_portal.db.session import get_db
from cr_portal.integrations.bitrix.client import BitrixClient
from cr_portal.repositories.users import UserRepository
async def db_session()->AsyncGenerator[AsyncSession,None]:
    async for s in get_db(): yield s
def bitrix_client(request:Request): return BitrixClient(request.session.get('bitrix_access_token'),request.session.get('bitrix_client_endpoint'))
async def current_user(request:Request,s:AsyncSession=Depends(db_session)):
    i=request.session.get('bitrix_user_id')
    if i is None: raise HTTPException(401,'Bitrix authorization required')
    u=await UserRepository(s).by_bitrix_id(int(i))
    if u is None: raise HTTPException(401,'User is not synchronized')
    return u
