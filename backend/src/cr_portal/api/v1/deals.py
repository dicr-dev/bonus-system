from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from cr_portal.api.deps import db_session
from cr_portal.repositories.deals import DealRepository
from cr_portal.schemas.deals import DealResponse
router=APIRouter()
@router.get('/',response_model=list[DealResponse])
async def deals(funnel:str|None=None,open_only:bool=False,s:AsyncSession=Depends(db_session)): return [DealResponse.model_validate(x) for x in await DealRepository(s).list(funnel=funnel,open_only=open_only)]
