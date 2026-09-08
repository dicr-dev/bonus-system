from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.models.deal import Deal
from cr_portal.services.app_settings import BusinessSettings
from cr_portal.services.bonus import raw_date


@dataclass(slots=True)
class SubscriptionDeals:
    implementation: list[Deal]
    cr_start: list[Deal]


@dataclass(slots=True)
class PlannedSubscriptionDeal:
    deal: Deal
    planned_date: date


def _next_month(value: date) -> date:
    return (
        date(value.year + 1, 1, 1)
        if value.month == 12
        else date(value.year, value.month + 1, 1)
    )


async def subscription_deals_for_month(
    session: AsyncSession,
    business: BusinessSettings,
    month: date,
    *,
    employee_id: UUID | None = None,
) -> SubscriptionDeals:
    """Return exactly the deals used by the dashboard subscription total."""
    following_month = _next_month(month)
    user_scope = (
        [] if employee_id is None else [Deal.implementation_responsible_user_id == employee_id]
    )

    implementation_result = await session.execute(
        select(Deal)
        .where(
            Deal.funnel == "implementation",
            Deal.status == "won",
            Deal.closed_time >= month,
            Deal.closed_time < following_month,
            *user_scope,
        )
        .order_by(Deal.closed_time, Deal.bitrix_id)
    )
    implementation = list(implementation_result.scalars().all())

    cr_start_result = await session.execute(
        select(Deal)
        .where(
            Deal.funnel == "cr_start",
            Deal.status == "in_progress",
            *user_scope,
        )
        .order_by(Deal.bitrix_id)
    )
    cr_start = [
        deal
        for deal in cr_start_result.scalars().all()
        if (
            commercial_use_date := raw_date(
                deal,
                business.field_cr_start_commercial_use_date,
            )
        )
        and month <= commercial_use_date < following_month
    ]

    return SubscriptionDeals(
        implementation=implementation,
        cr_start=cr_start,
    )


async def planned_subscription_deals_for_month(
    session: AsyncSession,
    business: BusinessSettings,
    month: date,
    *,
    employee_id: UUID | None = None,
) -> list[PlannedSubscriptionDeal]:
    following_month = _next_month(month)
    user_scope = (
        [] if employee_id is None else [Deal.implementation_responsible_user_id == employee_id]
    )
    result = await session.execute(
        select(Deal).where(
            Deal.funnel.in_(["tech_integration", "implementation"]),
            Deal.status == "in_progress",
            *user_scope,
        )
    )
    planned: list[PlannedSubscriptionDeal] = []
    for deal in result.scalars().all():
        planned_date = raw_date(deal, business.field_planned_subscription_date)
        if planned_date and month <= planned_date < following_month:
            planned.append(PlannedSubscriptionDeal(deal=deal, planned_date=planned_date))
    return sorted(planned, key=lambda item: (item.planned_date, item.deal.bitrix_id))
