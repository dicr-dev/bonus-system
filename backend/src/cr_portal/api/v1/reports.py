from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.api.deps import db_session
from cr_portal.models.deal import Deal, DealStatus, DealFunnel
from cr_portal.schemas.deals import DealResponse

router = APIRouter()


@router.get("/my-deals", response_model=list[DealResponse])
async def my_deals(
    session: AsyncSession = Depends(db_session),
) -> list[DealResponse]:
    from sqlalchemy import select

    result = await session.execute(
        select(Deal)
        .where(Deal.status == DealStatus.IN_PROGRESS)
        .order_by(Deal.created_at.desc())
    )
    return [DealResponse.model_validate(deal) for deal in result.scalars().all()]


@router.get("/implementation", response_model=list[DealResponse])
async def implementation_report(
    session: AsyncSession = Depends(db_session),
) -> list[DealResponse]:
    from sqlalchemy import select

    result = await session.execute(
        select(Deal)
        .where(Deal.funnel == DealFunnel.IMPLEMENTATION)
        .order_by(Deal.created_at.desc())
    )
    return [DealResponse.model_validate(deal) for deal in result.scalars().all()]
