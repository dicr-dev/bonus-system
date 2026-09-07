from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from cr_portal.api.deps import admin_user, db_session
from cr_portal.models.deal import Deal
from cr_portal.models.kpi import CalculationIssue
from cr_portal.schemas.kpi import IssueResponse
from cr_portal.services.bonus import diagnose_month
router=APIRouter()
def parse_month(v:str)->date:
    try:y,m=map(int,v.split("-"));return date(y,m,1)
    except Exception as e:raise HTTPException(422,"month must be YYYY-MM") from e

async def issue_responses(session:AsyncSession, month:date)->list[IssueResponse]:
    rows=await session.execute(select(CalculationIssue,Deal.bitrix_id).outerjoin(Deal,Deal.id==CalculationIssue.deal_id).where(CalculationIssue.month==month).order_by(CalculationIssue.severity,CalculationIssue.code))
    return [IssueResponse.model_validate(issue).model_copy(update={"deal_bitrix_id":bitrix_id}) for issue,bitrix_id in rows.all()]

@router.post("/run",response_model=list[IssueResponse])
async def run(month:str=Query(...),session:AsyncSession=Depends(db_session),_admin=Depends(admin_user)):
    parsed_month=parse_month(month);await diagnose_month(session,parsed_month);await session.commit();return await issue_responses(session,parsed_month)

@router.get("",response_model=list[IssueResponse])
async def issues(month:str=Query(...),session:AsyncSession=Depends(db_session),_admin=Depends(admin_user)):
    return await issue_responses(session,parse_month(month))
