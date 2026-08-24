from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from cr_portal.api.deps import db_session,current_user
from cr_portal.repositories.deals import DealRepository
from cr_portal.schemas.deals import DealResponse
router=APIRouter()
@router.get('/my-deals-in-work',response_model=list[DealResponse])
async def mine(u=Depends(current_user),s:AsyncSession=Depends(db_session)):
    allowed={'tech_integration','implementation','cr_start'}; return [DealResponse.model_validate(x) for x in await DealRepository(s).list(responsible_user_id=u.id,open_only=True) if x.funnel in allowed]
@router.get('/department-deals',response_model=list[DealResponse])
async def department(s:AsyncSession=Depends(db_session)): return [DealResponse.model_validate(x) for x in await DealRepository(s).list(open_only=True)]
