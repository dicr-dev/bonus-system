from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from cr_portal.api.deps import db_session
from cr_portal.models.kpi import CalculationIssue
from cr_portal.schemas.kpi import IssueResponse
from cr_portal.services.bonus import diagnose_month
router=APIRouter()
def parse_month(v:str)->date:
    try:y,m=map(int,v.split("-"));return date(y,m,1)
    except Exception as e:raise HTTPException(422,"month must be YYYY-MM") from e

@router.post("/run",response_model=list[IssueResponse])
async def run(month:str=Query(...),session:AsyncSession=Depends(db_session)):
    x=await diagnose_month(session,parse_month(month));await session.commit();return x

@router.get("",response_model=list[IssueResponse])
async def issues(month:str=Query(...),session:AsyncSession=Depends(db_session)):
    return list((await session.execute(select(CalculationIssue).where(CalculationIssue.month==parse_month(month)).order_by(CalculationIssue.severity,CalculationIssue.code))).scalars().all())
