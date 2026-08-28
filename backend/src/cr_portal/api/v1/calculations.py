from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from cr_portal.api.deps import db_session
from cr_portal.models.bonus import BonusCalculation, ManualBonusEvent
from cr_portal.models.deal import Deal
from cr_portal.models.user import User
from cr_portal.schemas.bonus import (
    CalculationDetail,
    CalculationItemResponse,
    CalculationResponse,
    ManualEventCreate,
    ManualEventResponse,
)
from cr_portal.services.bonus import calculate_month

router = APIRouter()


def parse_month(value: str) -> date:
    try:
        year, month = map(int, value.split("-"))
        return date(year, month, 1)
    except Exception as exc:
        raise HTTPException(422, "month must be YYYY-MM") from exc


async def _employee_names(
    session: AsyncSession,
    employee_ids: set[UUID],
) -> dict[UUID, str]:
    if not employee_ids:
        return {}

    result = await session.execute(
        select(User.id, User.full_name).where(User.id.in_(employee_ids))
    )
    return {user_id: full_name for user_id, full_name in result.all()}


def _calculation_response(
    calculation: BonusCalculation,
    employee_name: str | None,
) -> CalculationResponse:
    data = CalculationResponse.model_validate(calculation).model_dump()
    data["employee_name"] = employee_name
    return CalculationResponse(**data)


@router.post("/run", response_model=list[CalculationResponse])
async def run(
    month: str = Query(...),
    session: AsyncSession = Depends(db_session),
):
    calculations = await calculate_month(session, parse_month(month))
    names = await _employee_names(
        session,
        {calculation.employee_id for calculation in calculations},
    )
    return [
        _calculation_response(
            calculation,
            names.get(calculation.employee_id),
        )
        for calculation in calculations
    ]


@router.get("", response_model=list[CalculationResponse])
async def list_calculations(
    month: str = Query(...),
    session: AsyncSession = Depends(db_session),
):
    month_date = parse_month(month)

    result = await session.execute(
        select(BonusCalculation)
        .where(BonusCalculation.month == month_date)
        .order_by(
            BonusCalculation.employee_id,
            BonusCalculation.version.desc(),
        )
    )

    latest: dict[UUID, BonusCalculation] = {}
    for calculation in result.scalars().all():
        latest.setdefault(calculation.employee_id, calculation)

    calculations = list(latest.values())
    names = await _employee_names(
        session,
        {calculation.employee_id for calculation in calculations},
    )

    return [
        _calculation_response(
            calculation,
            names.get(calculation.employee_id),
        )
        for calculation in calculations
    ]


@router.get("/{calculation_id}", response_model=CalculationDetail)
async def detail(
    calculation_id: UUID,
    session: AsyncSession = Depends(db_session),
):
    result = await session.execute(
        select(BonusCalculation)
        .options(selectinload(BonusCalculation.items))
        .where(BonusCalculation.id == calculation_id)
    )
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

    base = CalculationResponse.model_validate(calculation).model_dump()
    base["employee_name"] = user.full_name

    return CalculationDetail(
        **base,
        items=items,
    )


@router.post("/manual-events", response_model=ManualEventResponse)
async def add_event(
    data: ManualEventCreate,
    session: AsyncSession = Depends(db_session),
):
    event = ManualBonusEvent(**data.model_dump())
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return event
