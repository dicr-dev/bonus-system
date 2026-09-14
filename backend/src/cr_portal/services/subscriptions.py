from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.models.deal import Deal
from cr_portal.services.app_settings import BusinessSettings
from cr_portal.services.bonus import linked_deal_ids, raw_date


@dataclass(slots=True)
class SubscriptionDeals:
    implementation: list[Deal]
    cr_start: list[Deal]


@dataclass(slots=True)
class PlannedSubscriptionDeal:
    deal: Deal
    planned_date: date


@dataclass(slots=True)
class PartialSubscriptionDeal:
    deal: Deal
    billing_start_date: date
    support_deal_created: bool


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


async def partial_subscription_deals(
    session: AsyncSession,
    business: BusinessSettings,
    *,
    employee_id: UUID | None = None,
) -> list[PartialSubscriptionDeal]:
    """Active implementation deals that already have a billing start date.

    A linked support deal is displayed as a status only, never as a filter.
    """
    user_scope = (
        [] if employee_id is None else [Deal.implementation_responsible_user_id == employee_id]
    )
    implementation_result = await session.execute(
        select(Deal).where(
            Deal.funnel == "implementation",
            Deal.status == "in_progress",
            *user_scope,
        )
    )
    candidates = [
        (deal, billing_start_date)
        for deal in implementation_result.scalars().all()
        if (billing_start_date := raw_date(deal, business.field_billing_start_date))
    ]
    if not candidates:
        return []

    support_result = await session.execute(
        select(Deal).where(Deal.funnel == "support")
    )
    implementation_ids_with_support = {
        source_id
        for support_deal in support_result.scalars().all()
        for source_id in linked_deal_ids(
            support_deal,
            business.field_source_deal_id,
        )
    }
    return [
        PartialSubscriptionDeal(
            deal=deal,
            billing_start_date=billing_start_date,
            support_deal_created=deal.bitrix_id in implementation_ids_with_support,
        )
        for deal, billing_start_date in sorted(candidates, key=lambda item: (item[1], item[0].bitrix_id))
    ]
