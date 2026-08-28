from datetime import date
from decimal import Decimal
from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from cr_portal.api.deps import current_user, db_session
from cr_portal.models.deal import Deal
from cr_portal.models.user import User
from cr_portal.repositories.deals import DealRepository
from cr_portal.schemas.dashboard import DashboardSummary, FunnelSummary, ResponsibleSummary
from cr_portal.schemas.deals import DealResponse
from cr_portal.services.app_settings import get_business_settings
from cr_portal.services.bonus import raw_date
router=APIRouter()

@router.get("/my-deals-in-work",response_model=list[DealResponse])
async def mine(user=Depends(current_user),session:AsyncSession=Depends(db_session)):
    r=await session.execute(select(Deal).where(Deal.implementation_responsible_user_id==user.id,Deal.status=="in_progress").order_by(Deal.bitrix_id.desc()))
    return [DealResponse.model_validate(x) for x in r.scalars().all()]

@router.get("/department-deals",response_model=list[DealResponse])
async def department(session:AsyncSession=Depends(db_session)):
    return [DealResponse.model_validate(x) for x in await DealRepository(session).list(open_only=True)]

@router.get("/dashboard",response_model=DashboardSummary)
async def dashboard(month: str | None = None, session:AsyncSession=Depends(db_session)):
    try:
        selected_month = date.fromisoformat(f"{month}-01") if month else date.today().replace(day=1)
    except ValueError:
        selected_month = date.today().replace(day=1)

    next_month = (
        date(selected_month.year + (selected_month.month == 12), selected_month.month % 12 + 1, 1)
    )
    business = await get_business_settings(session)
    implementation_amount = await session.scalar(
        select(func.coalesce(func.sum(Deal.opportunity), 0)).where(
            Deal.funnel == "implementation",
            Deal.status == "won",
            Deal.closed_time >= selected_month,
            Deal.closed_time < next_month,
        )
    )
    cr_start_amount = Decimal("0")
    cr_start_result = await session.execute(
        select(Deal).where(
            Deal.funnel == "cr_start",
            Deal.status == "in_progress",
        )
    )
    for deal in cr_start_result.scalars().all():
        commercial_use_date = raw_date(
            deal,
            business.field_cr_start_commercial_use_date,
        )
        if commercial_use_date and selected_month <= commercial_use_date < next_month:
            cr_start_amount += Decimal(deal.opportunity or 0)
    t=(await session.execute(select(func.count(Deal.id),func.coalesce(func.sum(Deal.monthly_amount),0),func.coalesce(func.sum(Deal.machines_count),0),func.count(Deal.id).filter(Deal.integration_1c.is_(True))).where(Deal.status=="in_progress"))).one()
    fr=await session.execute(select(Deal.funnel,func.count(Deal.id),func.coalesce(func.sum(Deal.monthly_amount),0),func.coalesce(func.sum(Deal.machines_count),0),func.count(Deal.id).filter(Deal.integration_1c.is_(True))).where(Deal.status=="in_progress").group_by(Deal.funnel).order_by(Deal.funnel))
    funnels=[FunnelSummary(funnel=x[0],active_deals=x[1],monthly_amount=Decimal(x[2] or 0),machines_count=int(x[3] or 0),integration_1c_deals=x[4]) for x in fr.all()]
    rr=await session.execute(select(User.id,User.full_name,func.count(Deal.id),func.coalesce(func.sum(Deal.monthly_amount),0),func.coalesce(func.sum(Deal.machines_count),0)).join(Deal,Deal.implementation_responsible_user_id==User.id).where(Deal.status=="in_progress").group_by(User.id,User.full_name).order_by(func.count(Deal.id).desc()))
    resp=[ResponsibleSummary(user_id=x[0],full_name=x[1],active_deals=x[2],monthly_amount=Decimal(x[3] or 0),machines_count=int(x[4] or 0)) for x in rr.all()]
    m=(await session.execute(select(func.count(Deal.id),func.coalesce(func.sum(Deal.monthly_amount),0),func.coalesce(func.sum(Deal.machines_count),0)).where(Deal.status=="in_progress",Deal.implementation_responsible_user_id.is_(None)))).one()
    if m[0]:resp.append(ResponsibleSummary(user_id=UUID(int=0),full_name="Без ответственного за внедрение",active_deals=m[0],monthly_amount=Decimal(m[1] or 0),machines_count=int(m[2] or 0)))
    implementation_amount = Decimal(implementation_amount or 0)
    return DashboardSummary(active_deals=t[0],monthly_amount=Decimal(t[1] or 0),machines_count=int(t[2] or 0),integration_1c_deals=t[3],subscription_implementation_amount=implementation_amount,subscription_cr_start_amount=cr_start_amount,subscription_total_amount=implementation_amount + cr_start_amount,funnels=funnels,responsibles=resp)
