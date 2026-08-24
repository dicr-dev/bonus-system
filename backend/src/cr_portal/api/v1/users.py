from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from cr_portal.api.deps import db_session,current_user
from cr_portal.repositories.users import UserRepository
from cr_portal.schemas.users import UserResponse
router=APIRouter()
@router.get('/me',response_model=UserResponse)
async def me(u=Depends(current_user)): return UserResponse.model_validate(u)
@router.get('/',response_model=list[UserResponse])
async def users(s:AsyncSession=Depends(db_session)): return [UserResponse.model_validate(x) for x in await UserRepository(s).list()]
