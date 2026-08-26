from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from cr_portal.api.deps import db_session
from cr_portal.models.kpi import MonthlyPlan
from cr_portal.schemas.kpi import KPISummary, PlanInput, PlanResponse
from cr_portal.services.kpi import kpi_summary
router=APIRouter()
def parse_month(v:str)->date:
    try:y,m=map(int,v.split("-"));return date(y,m,1)
    except Exception as e:raise HTTPException(422,"month must be YYYY-MM") from e

@router.get("/summary",response_model=KPISummary)
async def summary(month:str=Query(...),session:AsyncSession=Depends(db_session)):
    return await kpi_summary(session,parse_month(month))

@router.get("/plan",response_model=PlanResponse|None)
async def get_plan(month:str=Query(...),session:AsyncSession=Depends(db_session)):
    return (await session.execute(select(MonthlyPlan).where(MonthlyPlan.month==parse_month(month)))).scalar_one_or_none()

@router.put("/plan",response_model=PlanResponse)
async def put_plan(data:PlanInput,month:str=Query(...),session:AsyncSession=Depends(db_session)):
    m=parse_month(month);r=await session.execute(select(MonthlyPlan).where(MonthlyPlan.month==m));x=r.scalar_one_or_none()
    if x is None:x=MonthlyPlan(month=m,plan_value=data.plan_value,comment=data.comment);session.add(x)
    else:x.plan_value=data.plan_value;x.comment=data.comment
    await session.commit();await session.refresh(x);return x
