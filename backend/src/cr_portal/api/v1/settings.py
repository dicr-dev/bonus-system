import json
from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from cr_portal.api.deps import db_session
from cr_portal.models.bonus import BonusRule
from cr_portal.schemas.bonus import RuleCreate, RuleVersionResponse
router=APIRouter()

@router.get("/rules",response_model=list[RuleVersionResponse])
async def list_rules(session:AsyncSession=Depends(db_session)):
    return list((await session.execute(select(BonusRule).order_by(BonusRule.version.desc()))).scalars().all())

@router.post("/rules",response_model=RuleVersionResponse)
async def create_rule(data:RuleCreate,session:AsyncSession=Depends(db_session)):
    n=int((await session.execute(select(func.max(BonusRule.version)))).scalar_one_or_none() or 0)+1
    prev=(await session.execute(select(BonusRule).where(BonusRule.effective_to.is_(None)).order_by(BonusRule.version.desc()).limit(1))).scalar_one_or_none()
    if prev and prev.effective_from<data.effective_from:prev.effective_to=date.fromordinal(data.effective_from.toordinal()-1)
    x=BonusRule(version=n,effective_from=data.effective_from,config_json=json.dumps(data.config.model_dump(mode="json"),ensure_ascii=False),comment=data.comment)
    session.add(x);await session.commit();await session.refresh(x);return x
