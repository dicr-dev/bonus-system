from datetime import UTC, date, datetime, timedelta
from io import BytesIO
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Font
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.api.deps import admin_user, current_user, db_session
from cr_portal.models.deal import Deal
from cr_portal.models.user import User
from cr_portal.repositories.deals import DealRepository
from cr_portal.schemas.dashboard import DashboardSummary, FunnelSummary, ResponsibleSummary
from cr_portal.schemas.deals import DealResponse
from cr_portal.schemas.time_report import TimeReport
from cr_portal.schemas.task_1c_errors import Task1CErrorReport
from cr_portal.schemas.task_1c_check import Task1CCheckExportRequest, Task1CCheckReport
from cr_portal.services.app_settings import get_business_settings
from cr_portal.services.employee_scope import employee_is_in_kpi_department
from cr_portal.services.subscriptions import subscription_deals_for_month
from cr_portal.services.time_report import time_spent_report
from cr_portal.services.task_1c_errors import task_1c_errors_report
from cr_portal.services.task_1c_check import task_1c_check_report

router = APIRouter()


@router.get("/task-1c-check", response_model=Task1CCheckReport)
async def task_1c_check(
    user=Depends(admin_user),
    session: AsyncSession = Depends(db_session),
):
    return await task_1c_check_report(session)


@router.post("/task-1c-check/export")
async def export_task_1c_check(
    payload: Task1CCheckExportRequest,
    _user=Depends(admin_user),
    session: AsyncSession = Depends(db_session),
):
    rows = (await task_1c_check_report(session, task_bitrix_ids=payload.task_bitrix_ids))["tasks"]
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Проверка задач 1С"
    sheet.append(["№", "ID", "Название", "Сделка", "Воронка", "Постановщик", "Исполнитель", "Дата создания", "Задачи по 1С", "Тип задачи 1С", "Статус"])
    statuses = {1: "Новая", 2: "В работе", 3: "Выполняется", 4: "Ждёт контроля", 5: "Завершена", 6: "Отложена"}
    funnels = {"tech_integration": "Тех интеграция", "implementation": "Внедрение", "cr_start": "CR Start", "support": "Сопровождение"}
    for number, row in enumerate(rows, start=1):
        sheet.append([
            number, row["task_bitrix_id"], row["title"], row["deal_title"], funnels.get(row["deal_funnel"], row["deal_funnel"]), row["creator_name"], row["responsible_name"], row["created_time"],
            "Да" if row["in_1c_project"] else "Нет", "Заполнено" if row["has_1c_type"] else "Не заполнено",
            statuses.get(row["status"], "—"),
        ])
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for column in sheet.columns:
        sheet.column_dimensions[column[0].column_letter].width = min(60, max(14, max(len(str(cell.value or "")) for cell in column) + 2))
    sheet.freeze_panes = "A2"
    content = BytesIO()
    workbook.save(content)
    content.seek(0)
    return StreamingResponse(
        content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="task_1c_check.xlsx"'},
    )


@router.get("/time-spent", response_model=TimeReport)
async def time_spent(
    date_from: date = Query(...),
    date_to: date = Query(...),
    departments: list[str] = Query(default=[]),
    employee_ids: list[UUID] = Query(default=[]),
    funnels: list[str] = Query(default=[]),
    user=Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    try:
        return await time_spent_report(
            session,
            date_from=date_from,
            date_to=date_to,
            departments=departments,
            employee_ids=employee_ids,
            funnels=funnels,
            current_user=user,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/workplace-time", response_model=TimeReport)
async def workplace_time(
    user=Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    if not employee_is_in_kpi_department(user):
        raise HTTPException(403, "Workplace is available only to KPI department employees")

    date_to = datetime.now(ZoneInfo("Europe/Moscow")).date()
    return await time_spent_report(
        session,
        date_from=date_to - timedelta(days=9),
        date_to=date_to,
        departments=[],
        employee_ids=[],
        funnels=[],
        current_user=user,
        current_user_only=True,
    )


@router.get("/workplace-task-1c-errors", response_model=Task1CErrorReport)
async def workplace_task_1c_errors(
    employee_id: UUID | None = None,
    user=Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    try:
        return await task_1c_errors_report(
            session,
            current_user=user,
            employee_id=employee_id,
        )
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc


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

    business = await get_business_settings(session)
    user_scope = (
        [] if user.is_admin else [Deal.implementation_responsible_user_id == user.id]
    )
    active_deal_scope = [
        Deal.status == "in_progress",
        Deal.funnel.in_(("tech_integration", "implementation")),
        *user_scope,
    ]
    subscription_deals = await subscription_deals_for_month(
        session,
        business,
        selected_month,
        employee_id=None if user.is_admin else user.id,
    )
    implementation_amount = sum(
        (Decimal(deal.opportunity or 0) for deal in subscription_deals.implementation),
        Decimal(0),
    )
    cr_start_amount = sum(
        (Decimal(deal.opportunity or 0) for deal in subscription_deals.cr_start),
        Decimal(0),
    )

    totals = (
        await session.execute(
            select(
                func.count(Deal.id),
                func.coalesce(func.sum(Deal.monthly_amount), 0),
                func.coalesce(func.sum(Deal.machines_count), 0),
                func.count(Deal.id).filter(Deal.integration_1c.is_(True)),
            ).where(*active_deal_scope)
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
        .where(*active_deal_scope)
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
        .where(*active_deal_scope)
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
                    Deal.funnel.in_(("tech_integration", "implementation")),
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
