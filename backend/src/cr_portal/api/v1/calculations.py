from datetime import date
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from cr_portal.api.deps import db_session
from cr_portal.models.bonus import BonusCalculation, ManualBonusEvent
from cr_portal.models.user import User
from cr_portal.schemas.bonus import CalculationDetail, CalculationItemResponse, CalculationResponse, ManualEventCreate, ManualEventResponse
from cr_portal.services.bonus import calculate_month

router=APIRouter()
def parse_month(v:str)->date:
    try:y,m=map(int,v.split("-"));return date(y,m,1)
    except Exception as e:raise HTTPException(422,"month must be YYYY-MM") from e

@router.post("/run",response_model=list[CalculationResponse])
async def run(month:str=Query(...),session:AsyncSession=Depends(db_session)):
    return await calculate_month(session,parse_month(month))

@router.get("",response_model=list[CalculationResponse])
async def list_calculations(month:str=Query(...),session:AsyncSession=Depends(db_session)):
    m=parse_month(month);r=await session.execute(select(BonusCalculation).where(BonusCalculation.month==m).order_by(BonusCalculation.employee_id,BonusCalculation.version.desc()))
    latest={}
    for x in r.scalars().all():latest.setdefault(x.employee_id,x)
    return list(latest.values())

@router.get("/{calculation_id}",response_model=CalculationDetail)
async def detail(calculation_id:UUID,session:AsyncSession=Depends(db_session)):
    r=await session.execute(select(BonusCalculation).options(selectinload(BonusCalculation.items)).where(BonusCalculation.id==calculation_id));c=r.scalar_one_or_none()
    if c is None:raise HTTPException(404,"Calculation not found")
    u=(await session.execute(select(User).where(User.id==c.employee_id))).scalar_one()
    return CalculationDetail(**CalculationResponse.model_validate(c).model_dump(),employee_name=u.full_name,items=[CalculationItemResponse.model_validate(i) for i in c.items])

@router.post("/manual-events",response_model=ManualEventResponse)
async def add_event(data:ManualEventCreate,session:AsyncSession=Depends(db_session)):
    x=ManualBonusEvent(**data.model_dump());session.add(x);await session.commit();await session.refresh(x);return x
