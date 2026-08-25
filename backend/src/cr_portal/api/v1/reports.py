from decimal import Decimal
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from cr_portal.api.deps import current_user, db_session
from cr_portal.models.deal import Deal
from cr_portal.models.user import User
from cr_portal.repositories.deals import DealRepository
from cr_portal.schemas.dashboard import DashboardSummary, FunnelSummary, ResponsibleSummary
from cr_portal.schemas.deals import DealResponse
router = APIRouter()

@router.get("/my-deals-in-work", response_model=list[DealResponse])
async def my_deals_in_work(user=Depends(current_user), session: AsyncSession = Depends(db_session)):
    allowed = {"tech_integration", "implementation", "cr_start"}
    deals = await DealRepository(session).list(responsible_user_id=user.id, open_only=True)
    return [DealResponse.model_validate(deal) for deal in deals if deal.funnel in allowed]

@router.get("/department-deals", response_model=list[DealResponse])
async def department_deals(session: AsyncSession = Depends(db_session)):
    deals = await DealRepository(session).list(open_only=True)
    return [DealResponse.model_validate(deal) for deal in deals]

@router.get("/dashboard", response_model=DashboardSummary)
async def dashboard(session: AsyncSession = Depends(db_session)):
    totals_result = await session.execute(select(func.count(Deal.id), func.coalesce(func.sum(Deal.monthly_amount),0), func.coalesce(func.sum(Deal.machines_count),0), func.count(Deal.id).filter(Deal.integration_1c.is_(True))).where(Deal.status=="in_progress"))
    totals = totals_result.one()
    funnels_result = await session.execute(select(Deal.funnel, func.count(Deal.id), func.coalesce(func.sum(Deal.monthly_amount),0), func.coalesce(func.sum(Deal.machines_count),0), func.count(Deal.id).filter(Deal.integration_1c.is_(True))).where(Deal.status=="in_progress").group_by(Deal.funnel).order_by(Deal.funnel))
    funnels=[FunnelSummary(funnel=r[0], active_deals=r[1], monthly_amount=Decimal(r[2] or 0), machines_count=int(r[3] or 0), integration_1c_deals=r[4]) for r in funnels_result.all()]
    responsibles_result = await session.execute(select(User.id, User.full_name, func.count(Deal.id), func.coalesce(func.sum(Deal.monthly_amount),0), func.coalesce(func.sum(Deal.machines_count),0)).join(Deal, Deal.implementation_responsible_user_id==User.id).where(Deal.status=="in_progress").group_by(User.id, User.full_name).order_by(func.count(Deal.id).desc()))
    responsibles=[ResponsibleSummary(user_id=r[0], full_name=r[1], active_deals=r[2], monthly_amount=Decimal(r[3] or 0), machines_count=int(r[4] or 0)) for r in responsibles_result.all()]
    return DashboardSummary(active_deals=totals[0], monthly_amount=Decimal(totals[1] or 0), machines_count=int(totals[2] or 0), integration_1c_deals=totals[3], funnels=funnels, responsibles=responsibles)
