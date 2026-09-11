import json
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.models.deal import Deal
from cr_portal.models.kpi import KPIEvent, MonthlyPlan
from cr_portal.services.app_settings import get_business_settings
from cr_portal.services.subscriptions import (
    planned_subscription_deals_for_month,
    subscription_deals_for_month,
)


def month_start(value: date | datetime) -> date:
    if isinstance(value, datetime):
        value = value.date()
    return date(value.year, value.month, 1)


def next_month(value: date) -> date:
    return (
        date(value.year + 1, 1, 1)
        if value.month == 12
        else date(value.year, value.month + 1, 1)
    )


async def ensure_kpi_event(session: AsyncSession, deal: Deal) -> None:
    if (
        deal.status != "won"
        or deal.funnel not in {"implementation", "cr_start"}
        or deal.closed_time is None
    ):
        return
    event_type = "implementation_won" if deal.funnel == "implementation" else "cr_start_won"
    month = month_start(deal.closed_time)
    event_key = f"{event_type}:{deal.bitrix_id}:{month.isoformat()}"
    result = await session.execute(select(KPIEvent).where(KPIEvent.event_key == event_key))
    existing = result.scalar_one_or_none()
    if existing is not None:
        if existing.employee_id is None and deal.implementation_responsible_user_id is not None:
            existing.employee_id = deal.implementation_responsible_user_id
        return
    session.add(
        KPIEvent(
            event_key=event_key,
            month=month,
            event_date=deal.closed_time,
            event_type=event_type,
            employee_id=deal.implementation_responsible_user_id,
            deal_id=deal.id,
            value=Decimal(1),
            details_json=json.dumps(
                {"bitrix_id": deal.bitrix_id, "funnel": deal.funnel},
                ensure_ascii=False,
            ),
        )
    )


async def rebuild_missing_events(session: AsyncSession, month: date) -> None:
    start = month_start(month)
    end = next_month(start)
    result = await session.execute(
        select(Deal).where(
            Deal.status == "won",
            Deal.funnel.in_(["implementation", "cr_start"]),
            Deal.closed_time >= datetime(start.year, start.month, 1, tzinfo=UTC),
            Deal.closed_time < datetime(end.year, end.month, 1, tzinfo=UTC),
        )
    )
    for deal in result.scalars().all():
        await ensure_kpi_event(session, deal)
    await session.flush()


async def kpi_summary(
    session: AsyncSession,
    month: date,
    employee_id: UUID | None = None,
) -> dict:
    selected_month = month_start(month)
    plan_result = await session.execute(
        select(MonthlyPlan).where(MonthlyPlan.month == selected_month)
    )
    plan_row = plan_result.scalar_one_or_none()
    plan = plan_row.plan_value if plan_row else Decimal(0)

    business = await get_business_settings(session)
    deals = await subscription_deals_for_month(
        session,
        business,
        selected_month,
        employee_id=employee_id,
    )
    planned_deals = await planned_subscription_deals_for_month(
        session,
        business,
        selected_month,
        employee_id=employee_id,
    )

    def deal_item(deal: Deal) -> dict:
        return {
            "deal_id": deal.id,
            "bitrix_id": deal.bitrix_id,
            "title": deal.title,
            "amount": Decimal(deal.opportunity or 0),
        }

    implementation_total = sum(
        (Decimal(deal.opportunity or 0) for deal in deals.implementation),
        Decimal(0),
    )
    cr_start_total = sum(
        (Decimal(deal.opportunity or 0) for deal in deals.cr_start),
        Decimal(0),
    )
    fact = implementation_total + cr_start_total
    plan_completion_percent = (
        Decimal(0) if plan <= 0 else fact / plan * Decimal(100)
    )
    return {
        "month": selected_month,
        "plan": plan,
        "fact": fact,
        "plan_completion_percent": plan_completion_percent,
        "implementation_total": implementation_total,
        "cr_start_total": cr_start_total,
        "implementation_deals": [deal_item(deal) for deal in deals.implementation],
        "cr_start_deals": [deal_item(deal) for deal in deals.cr_start],
        "planned_deals": [
            {
                "deal_id": item.deal.id,
                "bitrix_id": item.deal.bitrix_id,
                "title": item.deal.title,
                "planned_date": item.planned_date,
                "amount": Decimal(item.deal.opportunity or 0),
                "machines_count": item.deal.machines_count,
            }
            for item in planned_deals
        ],
    }
