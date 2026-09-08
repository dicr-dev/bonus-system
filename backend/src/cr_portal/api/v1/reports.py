from datetime import UTC, date, datetime
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

router = APIRouter()


@router.get("/my-deals-in-work", response_model=list[DealResponse])
async def mine(
    user=Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    result = await session.execute(
        select(Deal)
        .where(
            Deal.implementation_responsible_user_id == user.id,
            Deal.status == "in_progress",
        )
        .order_by(Deal.bitrix_id.desc())
    )
    return [DealResponse.model_validate(deal) for deal in result.scalars().all()]


@router.get("/department-deals", response_model=list[DealResponse])
async def department(
    user=Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    if user.is_admin:
        deals = await DealRepository(session).list(open_only=True)
    else:
        result = await session.execute(
            select(Deal)
            .where(
                Deal.status == "in_progress",
                Deal.implementation_responsible_user_id == user.id,
            )
            .order_by(Deal.bitrix_id.desc())
        )
        deals = list(result.scalars().all())
    return [DealResponse.model_validate(deal) for deal in deals]


@router.get("/dashboard", response_model=DashboardSummary)
async def dashboard(
    month: str | None = None,
    user=Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    try:
        selected_month = (
            date.fromisoformat(f"{month}-01")
            if month
            else datetime.now(UTC).date().replace(day=1)
        )
    except ValueError:
        selected_month = datetime.now(UTC).date().replace(day=1)

    following_month = date(
        selected_month.year + (selected_month.month == 12),
        selected_month.month % 12 + 1,
        1,
    )
    business = await get_business_settings(session)
    user_scope = (
        [] if user.is_admin else [Deal.implementation_responsible_user_id == user.id]
    )

    implementation_amount = await session.scalar(
        select(func.coalesce(func.sum(Deal.opportunity), 0)).where(
            Deal.funnel == "implementation",
            Deal.status == "won",
            Deal.closed_time >= selected_month,
            Deal.closed_time < following_month,
            *user_scope,
        )
    )

    cr_start_amount = Decimal(0)
    cr_start_result = await session.execute(
        select(Deal).where(
            Deal.funnel == "cr_start",
            Deal.status == "in_progress",
            *user_scope,
        )
    )
    for deal in cr_start_result.scalars().all():
        commercial_use_date = raw_date(
            deal,
            business.field_cr_start_commercial_use_date,
        )
        if commercial_use_date and selected_month <= commercial_use_date < following_month:
            cr_start_amount += Decimal(deal.opportunity or 0)

    totals = (
        await session.execute(
            select(
                func.count(Deal.id),
                func.coalesce(func.sum(Deal.monthly_amount), 0),
                func.coalesce(func.sum(Deal.machines_count), 0),
                func.count(Deal.id).filter(Deal.integration_1c.is_(True)),
            ).where(Deal.status == "in_progress", *user_scope)
        )
    ).one()

    funnel_result = await session.execute(
        select(
            Deal.funnel,
            func.count(Deal.id),
            func.coalesce(func.sum(Deal.monthly_amount), 0),
            func.coalesce(func.sum(Deal.machines_count), 0),
            func.count(Deal.id).filter(Deal.integration_1c.is_(True)),
        )
        .where(Deal.status == "in_progress", *user_scope)
        .group_by(Deal.funnel)
        .order_by(Deal.funnel)
    )
    funnels = [
        FunnelSummary(
            funnel=row[0],
            active_deals=row[1],
            monthly_amount=Decimal(row[2] or 0),
            machines_count=int(row[3] or 0),
            integration_1c_deals=row[4],
        )
        for row in funnel_result.all()
    ]

    responsible_result = await session.execute(
        select(
            User.id,
            User.full_name,
            func.count(Deal.id),
            func.coalesce(func.sum(Deal.monthly_amount), 0),
            func.coalesce(func.sum(Deal.machines_count), 0),
        )
        .join(Deal, Deal.implementation_responsible_user_id == User.id)
        .where(Deal.status == "in_progress", *user_scope)
        .group_by(User.id, User.full_name)
        .order_by(func.count(Deal.id).desc())
    )
    responsibles = [
        ResponsibleSummary(
            user_id=row[0],
            full_name=row[1],
            active_deals=row[2],
            monthly_amount=Decimal(row[3] or 0),
            machines_count=int(row[4] or 0),
        )
        for row in responsible_result.all()
    ]

    if user.is_admin:
        missing = (
            await session.execute(
                select(
                    func.count(Deal.id),
                    func.coalesce(func.sum(Deal.monthly_amount), 0),
                    func.coalesce(func.sum(Deal.machines_count), 0),
                ).where(
                    Deal.status == "in_progress",
                    Deal.implementation_responsible_user_id.is_(None),
                )
            )
        ).one()
        if missing[0]:
            responsibles.append(
                ResponsibleSummary(
                    user_id=UUID(int=0),
                    full_name="Без ответственного за внедрение",
                    active_deals=missing[0],
                    monthly_amount=Decimal(missing[1] or 0),
                    machines_count=int(missing[2] or 0),
                )
            )

    implementation_amount = Decimal(implementation_amount or 0)
    return DashboardSummary(
        active_deals=totals[0],
        monthly_amount=Decimal(totals[1] or 0),
        machines_count=int(totals[2] or 0),
        integration_1c_deals=totals[3],
        subscription_implementation_amount=implementation_amount,
        subscription_cr_start_amount=cr_start_amount,
        subscription_total_amount=implementation_amount + cr_start_amount,
        funnels=funnels,
        responsibles=responsibles,
    )
