from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.models.deal import Deal
from cr_portal.models.employee_month_plan import EmployeeMonthlyDealPlan
from cr_portal.models.user import User
from cr_portal.services.app_settings import get_business_settings
from cr_portal.services.bonus import raw_value
from cr_portal.services.employee_scope import employee_is_in_department

MOSCOW = ZoneInfo("Europe/Moscow")
IMPLEMENTATION_DEPARTMENT = "Отдел внедрения"
ALLOWED_FUNNELS = ("tech_integration", "implementation")


def current_month() -> date:
    today = datetime.now(MOSCOW).date()
    return today.replace(day=1)


def _module_value(deal: Deal, field_name: str) -> str | None:
    value = raw_value(deal, field_name)
    if isinstance(value, list):
        value = ", ".join(str(item) for item in value if str(item).strip())
    value = str(value or "").strip()
    return value or None


def _item(deal: Deal, module_field: str) -> dict:
    return {
        "id": deal.id,
        "bitrix_id": deal.bitrix_id,
        "title": deal.title,
        "module": _module_value(deal, module_field),
        "machines_count": deal.machines_count,
        "integration_1c": deal.integration_1c,
        "opportunity": deal.opportunity,
        "monthly_amount": deal.monthly_amount,
    }


def _ensure_access(user: User) -> None:
    if not employee_is_in_department(user, IMPLEMENTATION_DEPARTMENT):
        raise PermissionError("План на месяц доступен только сотрудникам отдела внедрения")


async def employee_month_plan(session: AsyncSession, user: User) -> dict:
    _ensure_access(user)
    month = current_month()
    business = await get_business_settings(session)
    planned_deals = list(
        (
            await session.execute(
                select(Deal)
                .join(EmployeeMonthlyDealPlan, EmployeeMonthlyDealPlan.deal_id == Deal.id)
                .where(
                    EmployeeMonthlyDealPlan.employee_id == user.id,
                    EmployeeMonthlyDealPlan.month == month,
                )
                .order_by(Deal.title, Deal.bitrix_id)
            )
        ).scalars().all()
    )
    planned_ids = {deal.id for deal in planned_deals}
    available_deals = list(
        (
            await session.execute(
                select(Deal)
                .where(
                    Deal.implementation_responsible_user_id == user.id,
                    Deal.status == "in_progress",
                    Deal.funnel.in_(ALLOWED_FUNNELS),
                )
                .order_by(Deal.title, Deal.bitrix_id)
            )
        ).scalars().all()
    )
    return {
        "month": month,
        "available_deals": [_item(deal, business.field_module) for deal in available_deals if deal.id not in planned_ids],
        "planned_deals": [_item(deal, business.field_module) for deal in planned_deals],
    }


async def admin_employee_month_plan(session: AsyncSession) -> dict:
    month = current_month()
    business = await get_business_settings(session)
    rows = (
        await session.execute(
            select(User, Deal)
            .join(
                EmployeeMonthlyDealPlan,
                EmployeeMonthlyDealPlan.employee_id == User.id,
            )
            .join(Deal, EmployeeMonthlyDealPlan.deal_id == Deal.id)
            .where(EmployeeMonthlyDealPlan.month == month)
            .order_by(User.full_name, Deal.title, Deal.bitrix_id)
        )
    ).all()
    planned_deals = []
    for employee, deal in rows:
        item = _item(deal, business.field_module)
        item.update({"employee_id": employee.id, "employee_name": employee.full_name})
        planned_deals.append(item)
    return {"month": month, "planned_deals": planned_deals}


async def add_employee_month_plan_deal(
    session: AsyncSession, user: User, deal_id: UUID
) -> None:
    _ensure_access(user)
    month = current_month()
    deal = await session.get(Deal, deal_id)
    if (
        deal is None
        or deal.implementation_responsible_user_id != user.id
        or deal.status != "in_progress"
        or deal.funnel not in ALLOWED_FUNNELS
    ):
        raise LookupError("Доступна только своя активная сделка из Техинтеграции или Внедрения")
    exists = await session.scalar(
        select(EmployeeMonthlyDealPlan.id).where(
            EmployeeMonthlyDealPlan.month == month,
            EmployeeMonthlyDealPlan.employee_id == user.id,
            EmployeeMonthlyDealPlan.deal_id == deal_id,
        )
    )
    if exists is None:
        session.add(EmployeeMonthlyDealPlan(month=month, employee_id=user.id, deal_id=deal_id))
        await session.commit()


async def remove_employee_month_plan_deal(
    session: AsyncSession, user: User, deal_id: UUID
) -> None:
    _ensure_access(user)
    plan = await session.scalar(
        select(EmployeeMonthlyDealPlan).where(
            EmployeeMonthlyDealPlan.month == current_month(),
            EmployeeMonthlyDealPlan.employee_id == user.id,
            EmployeeMonthlyDealPlan.deal_id == deal_id,
        )
    )
    if plan is None:
        raise LookupError("Сделка не включена в план текущего месяца")
    await session.delete(plan)
    await session.commit()
