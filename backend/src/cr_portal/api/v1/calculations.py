from datetime import date
from decimal import Decimal
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from cr_portal.api.deps import admin_user, bitrix_client, current_user, db_session
from cr_portal.integrations.bitrix.client import BitrixClient
from cr_portal.models.bonus import (
    BonusCalculation,
    BonusCalculationItem,
    ManualBonusAdjustment,
    ManualBonusEvent,
)
from cr_portal.models.deal import Deal
from cr_portal.models.user import User
from cr_portal.schemas.bonus import (
    CalculationDetail,
    CalculationItemResponse,
    CalculationResponse,
    DealBonusOverrideCreate,
    DealBonusOverrideResponse,
    ManualBonusAdjustmentCreate,
    ManualBonusAdjustmentResponse,
    ManualEventCreate,
    ManualEventResponse,
)
from cr_portal.services.bonus import (
    CR_START_PERIOD_OVERRIDE,
    DEAL_OVERRIDE_EVENT_TYPES,
    IMPLEMENTATION_PERIOD_OVERRIDE,
    add_months,
    calculate_month,
    month_start,
)
from cr_portal.services.employee_scope import KPI_DEPARTMENT_NAMES, employee_is_in_kpi_department

router = APIRouter()


def parse_month(value: str) -> date:
    try:
        year, month = map(int, value.split("-"))
        return date(year, month, 1)
    except Exception as exc:
        raise HTTPException(422, "month must be YYYY-MM") from exc


async def _employee_details(
    session: AsyncSession,
    employee_ids: set[UUID],
) -> dict[UUID, tuple[str, str | None]]:
    if not employee_ids:
        return {}

    result = await session.execute(
        select(User.id, User.full_name, User.department_name).where(
            User.id.in_(employee_ids)
        )
    )
    return {
        user_id: (full_name, department_name)
        for user_id, full_name, department_name in result.all()
    }


def _calculation_response(
    calculation: BonusCalculation,
    employee: tuple[str, str | None] | None,
    extra_totals: dict[str, Decimal] | None = None,
) -> CalculationResponse:
    data = CalculationResponse.model_validate(calculation).model_dump()
    data["employee_name"] = employee[0] if employee else None
    data["employee_department"] = employee[1] if employee else None
    extra = extra_totals or {}
    data["overtime_hours"] = extra.get("overtime_hours", Decimal("0"))
    data["current_client_total"] = extra.get("current_client_total", Decimal("0"))
    data["kpi_total"] = extra.get("kpi_total", calculation.subtotal_dividable)
    data["kpi_divided_total"] = extra.get("kpi_divided_total", Decimal("0"))
    return CalculationResponse(**data)


async def _bonus_totals_by_calculation(
    session: AsyncSession,
    calculations: list[BonusCalculation],
) -> dict[UUID, dict[str, Decimal]]:
    if not calculations:
        return {}

    calculation_ids = [calculation.id for calculation in calculations]
    result = await session.execute(
        select(
            BonusCalculationItem.calculation_id,
            BonusCalculationItem.bonus_type,
            BonusCalculationItem.divider_applied,
            func.coalesce(func.sum(BonusCalculationItem.amount_final), Decimal("0")),
            func.coalesce(func.sum(BonusCalculationItem.quantity), Decimal("0")),
        )
        .where(BonusCalculationItem.calculation_id.in_(calculation_ids))
        .group_by(
            BonusCalculationItem.calculation_id,
            BonusCalculationItem.bonus_type,
            BonusCalculationItem.divider_applied,
        )
    )

    totals: dict[UUID, dict[str, Decimal]] = {
        calculation.id: {
            "overtime_hours": Decimal("0"),
            "current_client_total": Decimal("0"),
            "kpi_total": calculation.subtotal_dividable,
            "kpi_divided_total": Decimal("0"),
        }
        for calculation in calculations
    }

    for calculation_id, bonus_type, divider_applied, amount, quantity in result.all():
        amount_decimal = Decimal(str(amount or 0))
        quantity_decimal = Decimal(str(quantity or 0))
        if divider_applied:
            totals[calculation_id]["kpi_divided_total"] += amount_decimal
        if bonus_type == "overtime_hours":
            totals[calculation_id]["overtime_hours"] += quantity_decimal
        if bonus_type == "current_client":
            totals[calculation_id]["current_client_total"] += amount_decimal

    return totals


@router.post("/run", response_model=list[CalculationResponse])
async def run(
    month: str = Query(...),
    session: AsyncSession = Depends(db_session),
    _admin=Depends(admin_user),
    client: BitrixClient = Depends(bitrix_client),
):
    try:
        calculations = await calculate_month(session, parse_month(month), client=client)
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(422, str(exc)) from exc
    except (httpx.HTTPError, RuntimeError) as exc:
        await session.rollback()
        raise HTTPException(502, "Не удалось получить данные задач Битрикс24. Расчёт не сохранён.") from exc
    employees = await _employee_details(
        session,
        {calculation.employee_id for calculation in calculations},
    )
    totals = await _bonus_totals_by_calculation(session, calculations)
    return [
        _calculation_response(
            calculation,
            employees.get(calculation.employee_id),
            totals.get(calculation.id),
        )
        for calculation in calculations
    ]


@router.get("", response_model=list[CalculationResponse])
async def list_calculations(
    month: str = Query(...),
    session: AsyncSession = Depends(db_session),
    user=Depends(current_user),
):
    month_date = parse_month(month)

    query = (
        select(BonusCalculation)
        .join(User, User.id == BonusCalculation.employee_id)
        .where(BonusCalculation.month == month_date)
        .where(
            User.is_active.is_(True),
            or_(
                *(
                    User.department_name.contains(department_name)
                    for department_name in KPI_DEPARTMENT_NAMES
                )
            ),
        )
        .order_by(
            BonusCalculation.employee_id,
            BonusCalculation.version.desc(),
        )
    )
    if not user.is_admin:
        query = query.where(BonusCalculation.employee_id == user.id)
    result = await session.execute(query)

    latest: dict[UUID, BonusCalculation] = {}
    for calculation in result.scalars().all():
        latest.setdefault(calculation.employee_id, calculation)

    calculations = list(latest.values())
    employees = await _employee_details(
        session,
        {calculation.employee_id for calculation in calculations},
    )
    totals = await _bonus_totals_by_calculation(session, calculations)

    return [
        _calculation_response(
            calculation,
            employees.get(calculation.employee_id),
            totals.get(calculation.id),
        )
        for calculation in calculations
    ]


def _deal_override_response(
    event: ManualBonusEvent,
    deal: Deal,
    employee: User,
) -> DealBonusOverrideResponse:
    start_month = month_start(event.event_date)
    months = max(int(event.quantity), 1)
    return DealBonusOverrideResponse(
        id=event.id,
        deal_id=deal.id,
        deal_bitrix_id=deal.bitrix_id,
        deal_title=deal.title,
        funnel=deal.funnel,
        employee_id=employee.id,
        employee_name=employee.full_name,
        start_month=start_month,
        end_month=add_months(start_month, months - 1),
        months=months,
        calculation_mode=event.calculation_mode,
        amount=(event.amount if event.calculation_mode == "manual_amount" else None),
        comment=event.comment,
        created_at=event.created_at,
    )


@router.get("/deal-overrides", response_model=list[DealBonusOverrideResponse])
async def list_deal_overrides(
    session: AsyncSession = Depends(db_session),
    _admin=Depends(admin_user),
):
    result = await session.execute(
        select(ManualBonusEvent, Deal, User)
        .join(Deal, Deal.id == ManualBonusEvent.deal_id)
        .join(User, User.id == ManualBonusEvent.employee_id)
        .where(ManualBonusEvent.event_type.in_(DEAL_OVERRIDE_EVENT_TYPES))
        .order_by(ManualBonusEvent.event_date.desc(), Deal.bitrix_id)
    )
    return [
        _deal_override_response(event, deal, employee)
        for event, deal, employee in result.all()
    ]


@router.post("/deal-overrides", response_model=DealBonusOverrideResponse)
async def save_deal_override(
    data: DealBonusOverrideCreate,
    session: AsyncSession = Depends(db_session),
    _admin=Depends(admin_user),
):
    deal = (
        await session.execute(select(Deal).where(Deal.bitrix_id == data.deal_bitrix_id))
    ).scalar_one_or_none()
    if deal is None:
        raise HTTPException(404, "Сделка не найдена. Сначала выполните синхронизацию.")
    event_type_by_funnel = {
        "cr_start": CR_START_PERIOD_OVERRIDE,
        "implementation": IMPLEMENTATION_PERIOD_OVERRIDE,
    }
    event_type = event_type_by_funnel.get(deal.funnel)
    if event_type is None:
        raise HTTPException(422, "Корректировка доступна только для сделок CR Start и Внедрения.")
    if data.calculation_mode == "manual_amount" and data.amount is None:
        raise HTTPException(422, "Укажите сумму ручной корректировки.")

    employee = await session.get(User, data.employee_id)
    if employee is None or not employee.is_active or not employee_is_in_kpi_department(employee):
        raise HTTPException(422, "Выберите активного сотрудника отдела внедрения или Разработки 1С.")

    event = (
        await session.execute(
            select(ManualBonusEvent).where(
                ManualBonusEvent.deal_id == deal.id,
                ManualBonusEvent.event_type == event_type,
            )
        )
    ).scalar_one_or_none()
    if event is None:
        event = ManualBonusEvent(
            event_date=month_start(data.start_month),
            employee_id=employee.id,
            deal_id=deal.id,
            event_type=event_type,
            quantity=Decimal(data.months),
            amount=Decimal(data.amount or 0),
            calculation_mode=data.calculation_mode,
            comment=data.comment,
        )
        session.add(event)
    else:
        event.event_date = month_start(data.start_month)
        event.employee_id = employee.id
        event.quantity = Decimal(data.months)
        event.amount = Decimal(data.amount or 0)
        event.calculation_mode = data.calculation_mode
        event.comment = data.comment

    await session.commit()
    await session.refresh(event)
    return _deal_override_response(event, deal, employee)


@router.delete("/deal-overrides/{override_id}", status_code=204)
async def delete_deal_override(
    override_id: UUID,
    session: AsyncSession = Depends(db_session),
    _admin=Depends(admin_user),
):
    event = await session.get(ManualBonusEvent, override_id)
    if event is None or event.event_type not in DEAL_OVERRIDE_EVENT_TYPES:
        raise HTTPException(404, "Корректировка не найдена.")
    await session.delete(event)
    await session.commit()


def _manual_adjustment_response(
    adjustment: ManualBonusAdjustment,
    employee: User,
) -> ManualBonusAdjustmentResponse:
    start_month = month_start(adjustment.start_month)
    return ManualBonusAdjustmentResponse(
        id=adjustment.id,
        employee_id=employee.id,
        employee_name=employee.full_name,
        title=adjustment.title,
        start_month=start_month,
        end_month=add_months(start_month, adjustment.months - 1),
        months=adjustment.months,
        amount=adjustment.amount,
        comment=adjustment.comment,
        created_at=adjustment.created_at,
    )


@router.get("/manual-adjustments", response_model=list[ManualBonusAdjustmentResponse])
async def list_manual_adjustments(
    session: AsyncSession = Depends(db_session),
    _admin=Depends(admin_user),
):
    result = await session.execute(
        select(ManualBonusAdjustment, User)
        .join(User, User.id == ManualBonusAdjustment.employee_id)
        .order_by(ManualBonusAdjustment.start_month.desc(), ManualBonusAdjustment.created_at.desc())
    )
    return [
        _manual_adjustment_response(adjustment, employee)
        for adjustment, employee in result.all()
    ]


@router.post("/manual-adjustments", response_model=ManualBonusAdjustmentResponse)
async def save_manual_adjustment(
    data: ManualBonusAdjustmentCreate,
    session: AsyncSession = Depends(db_session),
    _admin=Depends(admin_user),
):
    if data.amount == 0:
        raise HTTPException(422, "Сумма бонуса или штрафа не может быть нулевой.")
    employee = await session.get(User, data.employee_id)
    if employee is None or not employee.is_active or not employee_is_in_kpi_department(employee):
        raise HTTPException(422, "Выберите активного сотрудника отдела внедрения или Разработки 1С.")
    adjustment = ManualBonusAdjustment(
        employee_id=employee.id,
        title=data.title.strip(),
        start_month=month_start(data.start_month),
        months=data.months,
        amount=data.amount,
        comment=data.comment,
    )
    session.add(adjustment)
    await session.commit()
    await session.refresh(adjustment)
    return _manual_adjustment_response(adjustment, employee)


@router.put("/manual-adjustments/{adjustment_id}", response_model=ManualBonusAdjustmentResponse)
async def update_manual_adjustment(
    adjustment_id: UUID,
    data: ManualBonusAdjustmentCreate,
    session: AsyncSession = Depends(db_session),
    _admin=Depends(admin_user),
):
    if data.amount == 0:
        raise HTTPException(422, "Сумма бонуса или штрафа не может быть нулевой.")
    adjustment = await session.get(ManualBonusAdjustment, adjustment_id)
    if adjustment is None:
        raise HTTPException(404, "Ручной бонус или штраф не найден.")
    employee = await session.get(User, data.employee_id)
    if employee is None or not employee.is_active or not employee_is_in_kpi_department(employee):
        raise HTTPException(422, "Выберите активного сотрудника отдела внедрения или Разработки 1С.")
    adjustment.employee_id = employee.id
    adjustment.title = data.title.strip()
    adjustment.start_month = month_start(data.start_month)
    adjustment.months = data.months
    adjustment.amount = data.amount
    adjustment.comment = data.comment
    await session.commit()
    await session.refresh(adjustment)
    return _manual_adjustment_response(adjustment, employee)


@router.delete("/manual-adjustments/{adjustment_id}", status_code=204)
async def delete_manual_adjustment(
    adjustment_id: UUID,
    session: AsyncSession = Depends(db_session),
    _admin=Depends(admin_user),
):
    adjustment = await session.get(ManualBonusAdjustment, adjustment_id)
    if adjustment is None:
        raise HTTPException(404, "Ручной бонус или штраф не найден.")
    await session.delete(adjustment)
    await session.commit()


@router.get("/{calculation_id}", response_model=CalculationDetail)
async def detail(
    calculation_id: UUID,
    session: AsyncSession = Depends(db_session),
    user=Depends(current_user),
):
    query = (
        select(BonusCalculation)
        .options(selectinload(BonusCalculation.items))
        .where(BonusCalculation.id == calculation_id)
    )
    if not user.is_admin:
        query = query.where(BonusCalculation.employee_id == user.id)
    result = await session.execute(query)
    calculation = result.scalar_one_or_none()

    if calculation is None:
        raise HTTPException(404, "Calculation not found")

    user = (
        await session.execute(
            select(User).where(User.id == calculation.employee_id)
        )
    ).scalar_one()

    deal_ids = {
        item.deal_id
        for item in calculation.items
        if item.deal_id is not None
    }

    deals: dict[UUID, Deal] = {}
    if deal_ids:
        deal_result = await session.execute(
            select(Deal).where(Deal.id.in_(deal_ids))
        )
        deals = {deal.id: deal for deal in deal_result.scalars().all()}

    items: list[CalculationItemResponse] = []
    for item in calculation.items:
        deal = deals.get(item.deal_id) if item.deal_id else None
        data = CalculationItemResponse.model_validate(item).model_dump()
        data["deal_title"] = deal.title if deal else None
        data["deal_bitrix_id"] = deal.bitrix_id if deal else None
        items.append(CalculationItemResponse(**data))

    totals = await _bonus_totals_by_calculation(session, [calculation])
    base = _calculation_response(
        calculation,
        (user.full_name, user.department_name),
        totals.get(calculation.id),
    ).model_dump()
    base["employee_name"] = user.full_name

    return CalculationDetail(
        **base,
        items=items,
    )


@router.post("/manual-events", response_model=ManualEventResponse)
async def add_event(
    data: ManualEventCreate,
    session: AsyncSession = Depends(db_session),
    _admin=Depends(admin_user),
):
    event = ManualBonusEvent(**data.model_dump())
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return event
