from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from io import BytesIO
from pydantic import BaseModel, Field
from fastapi.responses import StreamingResponse
from cr_portal.services.employee_plan_export import employee_plan_excel

from cr_portal.api.deps import admin_user, current_user, db_session
from cr_portal.schemas.employee_month_plan import AdminEmployeeMonthPlan, EmployeeMonthPlan, EmployeeMonthPlanAdd
from cr_portal.services.employee_month_plan import (
    add_employee_month_plan_deal,
    admin_employee_month_plan,
    employee_month_plan,
    remove_employee_month_plan_deal,
)

router = APIRouter()


class PlanExportInput(BaseModel):
    keys: list[str] | None = Field(default=None, max_length=10000)


@router.post('/admin/export')
async def export_admin_plan(data: PlanExportInput, _admin=Depends(admin_user), session=Depends(db_session)):
    plan=AdminEmployeeMonthPlan.model_validate(await admin_employee_month_plan(session))
    content=employee_plan_excel(plan,data.keys)
    return StreamingResponse(BytesIO(content),media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':f'attachment; filename="employee_plans_{plan.month}.xlsx"','Cache-Control':'no-store'})


@router.get("/admin", response_model=AdminEmployeeMonthPlan)
async def get_admin_plan(
    _admin=Depends(admin_user), session: AsyncSession = Depends(db_session)
):
    return await admin_employee_month_plan(session)


@router.get("/", response_model=EmployeeMonthPlan)
async def get_plan(user=Depends(current_user), session: AsyncSession = Depends(db_session)):
    try:
        return await employee_month_plan(session, user)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc


@router.post("/", status_code=204)
async def add_plan_deal(
    data: EmployeeMonthPlanAdd,
    user=Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    try:
        await add_employee_month_plan_deal(session, user, data.deal_id)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.delete("/{deal_id}", status_code=204)
async def remove_plan_deal(
    deal_id: UUID,
    user=Depends(current_user),
    session: AsyncSession = Depends(db_session),
):
    try:
        await remove_employee_month_plan_deal(session, user, deal_id)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
