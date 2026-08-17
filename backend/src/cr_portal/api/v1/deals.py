from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.api.deps import db_session
from cr_portal.models.deal import DealFunnel
from cr_portal.repositories.deal import DealRepository
from cr_portal.schemas.deals import DealResponse

router = APIRouter()


@router.get("/", response_model=list[DealResponse])
async def list_deals(
    funnel: DealFunnel | None = None,
    session: AsyncSession = Depends(db_session),
) -> list[DealResponse]:
    deals = await DealRepository(session).list(funnel)
    return [DealResponse.model_validate(deal) for deal in deals]
